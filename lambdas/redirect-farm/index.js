'use strict';

exports.handler = (event, context, callback) => {
    const response = {
        status: '301',
        statusDescription: 'Moved Permanently',
        headers: {
            location: [{
                key: 'Location',
                value: 'https://dev.azure.com/openttd/OpenTTD/_build',
            }],
        },
    };
    callback(null, response);
};
