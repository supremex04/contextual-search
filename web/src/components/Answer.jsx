import React from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faBook, faGlobe, faSearch, faLightbulb, faLink } from '@fortawesome/free-solid-svg-icons';

const Answer = ({ history, loading }) => {
    return (
        <div className="flex flex-col items-center justify-center w-full max-w-4xl p-6 space-y-6 h-full">
            {loading && <div className="loader"></div>}
            {history.length > 0 ? (
                <div className="flex flex-col space-y-12 w-full max-w-4xl">
                    {history.map((item, index) => (
                        <div key={index} className="relative bg-gray-800 p-4 rounded-2xl shadow-lg transition transform hover:scale-101 duration-200">
                            <div className="icon-container absolute top-4 right-4">
                                {item.urls && item.urls.length > 0 ? (
                                    <FontAwesomeIcon icon={faGlobe} className="icon text-blue-500" />
                                ) : (
                                    <FontAwesomeIcon icon={faBook} className="icon text-blue-500" />
                                )}
                            </div>
                            <div className="flex items-start space-x-2 pr-10 mb-4">
                                <FontAwesomeIcon icon={faSearch} className="text-blue-500 mt-1" />
                                <p className="mb-2 font-semibold text-left">{item.question}</p>
                            </div>
                            <div className="flex items-start space-x-2 pr-10 mb-6">
                                <FontAwesomeIcon icon={faLightbulb} className="text-yellow-500 mt-1" />
                                <div className="text-left text-gray-200" dangerouslySetInnerHTML={{ __html: item.answer }}></div>
                            </div>
                            {item.urls && item.urls.length > 0 && (
                                <div className="url-list mt-4">
                                    <div className="flex items-start space-x-2">
                                        <FontAwesomeIcon icon={faLink} className="text-blue-500 mt-1" />
                                        <p className="text-left text-sm font-semibold">References:</p>
                                    </div>
                                    <ul className="text-sm mt-2 list-disc pl-5">
                                        {item.urls.map((url, urlIndex) => (
                                            <li key={urlIndex} className="text-left">
                                                <a href={url} className="text-blue-400" target="_blank" rel="noopener noreferrer">{url}</a>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            ) : (
                <p className="text-gray-500"></p>
            )}
        </div>
    );
};

export default Answer;