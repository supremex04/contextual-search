from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_groq import ChatGroq
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.graph import StateGraph
from langchain.schema import Document
from llama_index.llms.groq import Groq
from llama_index.core import Settings, VectorStoreIndex, StorageContext
from llama_index.vector_stores.qdrant import QdrantVectorStore
import qdrant_client
from typing_extensions import TypedDict
from typing import List
import nest_asyncio

# Load environment variables from .env file
load_dotenv()

# Initialize FastEmbedEmbeddings model
embed_model = FastEmbedEmbeddings(model_name="BAAI/bge-base-en-v1.5")

# Initialize Flask app and enable CORS
server_app = Flask(__name__)
CORS(server_app)

# Apply nest_asyncio to enable async within Flask
nest_asyncio.apply()

# Set environment variables
os.environ['LLAMA_PARSE_API_KEY'] = os.getenv("LLAMA_API_KEY")
os.environ['GROQ_API_KEY'] = os.getenv("GROQ_API_KEY")
os.environ['LANGCHAIN_TRACING-V2'] = 'true'
os.environ['LANGCHAIN_ENDPOINT'] = 'https://api.smith.langchain.com'
os.environ['LANGCHAIN_API_KEY'] = os.getenv("LANGCHAIN_API_KEY")
os.environ['TAVILY_API_KEY'] = os.getenv("TAVILY_API_KEY")

# Initialize LlamaParse with API key and load documents
from llama_parse import LlamaParse
llama_parse_documents = LlamaParse(api_key=os.getenv("LLAMA_PARSE_API_KEY"), result_type="markdown").load_data(["./context/medilens/cardio_vascular.pdf"])

# Initialize Groq model
llm1 = Groq(model="Llama3-8b-8192", api_key=os.getenv("GROQ_API_KEY"))

# Set settings for llm and embed_model
Settings.llm = llm1
Settings.embed_model = embed_model

# Initialize QdrantClient for vector store
client = qdrant_client.QdrantClient(
    "https://b419f947-f8a1-4c31-bfcf-6c0ca299eed5.us-east4-0.gcp.cloud.qdrant.io",
    api_key=os.getenv("QDRANT_API_KEY")
)

# Initialize vector store and storage context
vector_store = QdrantVectorStore(client=client, collection_name="legal_documents")
storage_context = StorageContext.from_defaults(vector_store=vector_store)

# Build index from documents
index = VectorStoreIndex.from_documents(documents=llama_parse_documents, storage_context=storage_context, show_progress=True)

# Initialize retriever with k=3 for search
retriever = index.as_retriever(search_kwargs={"k": 3})

# Initialize ChatGroq for question answering
llm = ChatGroq(
    temperature=0,
    model="Llama3-8b-8192",
    api_key=os.getenv("GROQ_API_KEY")
)

# Generation prompt template
generation_prompt = PromptTemplate(
    template="""system You are an assistant for question-answering tasks. Only
    Use the following pieces of retrieved context to answer the question. If context does not provide information to answer that question, just say user to do web search.
    If the context provides needed information to answer the question, use it to answer the question keeping the answer concise. user
    Question: {question}
    Context: {context}
    Answer: assistant""",
    input_variables=["question", "document"],
)

# Post-processing
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# Chain
rag_chain = generation_prompt | llm | StrOutputParser()

# Answer grading prompt template
grading_prompt = PromptTemplate(
    template="""system You are a grader assessing whether an
    answer is useful to resolve a question. Give a score 'yes' or 'no' to indicate whether the answer is
    useful to resolve a question. Provide the binary score as a JSON with a single key 'score' and no preamble or explanation.
    user Here is the answer:
    \n ------- \n
    {generation}
    \n ------- \n
    Here is the question: {question} assistant""",
    input_variables=["generation", "question"],
)

# Chain for answer grading
answer_grader = grading_prompt | llm | JsonOutputParser()

# Initialize TavilySearchResults for web search tool with k=3
web_search_tool = TavilySearchResults(k=3)

# Define GraphState TypedDict
class GraphState(TypedDict):
    question: str
    generation: str
    web_search: str
    documents: List[str]

# Define generate function for StateGraph
def generate(state):
    question = state["question"]
    documents = state.get("documents", [])

    # Query engine for retrieving documents
    query_engine = index.as_query_engine()
    generation = query_engine.query(question).response
    print("GENERATING FROM CONTEXT")

    # Evaluate score using answer grader
    score = answer_grader.invoke({"question": question, "generation": generation})
    print(score['score'])

    if score['score'] == 'yes':
        print("CONTEXT RESPONSE IS OK")
        return {"documents": documents, "question": question, "generation": generation}

    print("DOING WEB SEARCH")
    while score['score'] == 'no':
        try:
            docs = web_search_tool.invoke({"query": question})
            print(docs)
            if docs:
                web_results = "\n".join([d["content"] for d in docs])
                web_results = Document(page_content=web_results)
                if documents is not None:
                    documents.append(web_results)
                else:
                    documents = [web_results]

                generation = rag_chain.invoke({"context": format_docs(documents), "question": question})
                print("GENERATING FROM WEB_SEARCH")

                score = answer_grader.invoke({"question": question, "generation": generation})
                if score['score'] == 'yes':
                    print("WEB SEARCH RESULT IS OK")
                    return {"documents": documents, "question": question, "generation": generation}
            else:
                print("WEB SEARCH RETURNED NO RESULTS")
                return {"documents": documents, "question": question, "generation": "Sorry, I couldn't find any information."}
        except Exception as e:
            print(f"WEB SEARCH FAILED: {e}")
            return {"documents": documents, "question": question, "generation": "Sorry, an error occurred during the web search."}
# Initialize StateGraph workflow
workflow = StateGraph(GraphState)
workflow.add_node("generate", generate)
workflow.set_entry_point("generate")
workflow.set_finish_point("generate")

# Compile app from StateGraph
app = workflow.compile()

# Route to handle POST requests to '/query'
@server_app.route('/query', methods=['POST'])
def query():
    data = request.json
    question = data['question']
    print(f"Received question: {question}")
    inputs = {"question": question}
    output = None
    for output in app.stream(inputs):
        for key, value in output.items():
            print(f"Finished running: {key}")
    print(f"Generated answer: {value['generation']}")
    return jsonify({"generation": value["generation"]})

# Main entry point of the application
if __name__ == "__main__":
    server_app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)
