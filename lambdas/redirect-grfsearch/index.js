'use strict';

const querystring = require('querystring');

exports.handler = (event, context, callback) => {
    var request = event.Records[0].cf.request;
    const params = querystring.parse(request.querystring);

    var redirect_uri = '/index.php';

    if (params.q) {
        var redirect_params;

        if (params.do == 'searchtext') {
            redirect_params = {
                do: 'search',
                q: params.q,
            };
        }
        if (params.do == 'searchgrfid') {
            redirect_params = {
                do: 'search',
                type: 'grfidlist',
                /* grfcrawler does not support md5sum, so remove them from the query */
                q: params.q.replace(/:[0-9A-Fa-f]*/g, ''),
            };
        }

        redirect_uri += "?" + querystring.stringify(redirect_params);
    }

    const response = {
        status: '301',
        statusDescription: 'Moved Permanently',
        headers: {
            location: [{
                key: 'Location',
                value: 'https://grfcrawler.tt-forums.net' + redirect_uri,
            }],
        },
    };
    callback(null, response);
    return;
};
