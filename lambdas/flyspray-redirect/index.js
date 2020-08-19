'use strict';

exports.handler = (event, context, callback) => {
    var request = event.Records[0].cf.request;
    var olduri = request.uri;

    if (olduri == "/" || olduri == "/index.html") {
        const response = {
            status: '301',
            statusDescription: 'Moved Permanently',
            headers: {
                location: [{
                    key: 'Location',
                    value: 'https://github.com/OpenTTD/OpenTTD/issues',
                }],
            },
        };
        callback(null, response);
        return;
    }

    var newuri = olduri.replace(/^\/task\/([0-9]+)$/, '\/task\/$1.html');
    request.uri = newuri;

    return callback(null, request);
};
