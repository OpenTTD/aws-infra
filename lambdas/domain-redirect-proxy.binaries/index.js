'use strict';

exports.handler = (event, context, callback) => {
    var request = event.Records[0].cf.request;

    const response = {
        status: '301',
        statusDescription: 'Moved Permanently',
        headers: {
            location: [{
                key: 'Location',
                value: 'https://cdn.openttd.org' + (request.uri ? request.uri : '/'),
            }],
        },
    };
    callback(null, response);
};
