'use strict';

exports.handler = (event, context, callback) => {
    const response = {
        status: '301',
        statusDescription: 'Moved Permanently',
        headers: {
            location: [{
                key: 'Location',
                value: 'https://www.tt-forums.net/viewforum.php?f=55',
            }],
        },
    };
    callback(null, response);
};
