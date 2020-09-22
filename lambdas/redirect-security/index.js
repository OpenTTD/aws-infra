'use strict';

exports.handler = (event, context, callback) => {
    var request = event.Records[0].cf.request;
    var uri = request.uri;

    var redirect_uri;

    if (uri == '/' || uri == '/en' || uri == '/en/') {
        redirect_uri = '/security.html';
    } else if (/^\/en\/CVE/.test(uri)) {
        redirect_uri = uri.replace(/^\/en\/CVE-([0-9]+)-([0-9]+)$/, '\/security\/CVE-$1-$2.html');
    } else if (/^\/CVE/.test(uri)) {
        redirect_uri = uri.replace(/^\/CVE-([0-9]+)-([0-9]+)$/, '\/security\/CVE-$1-$2.html');
    } else {
        /* We have no clue what the user tried to visit, so just point him to the main page */
        redirect_uri = '/security.html';
    }

    const response = {
        status: '301',
        statusDescription: 'Moved Permanently',
        headers: {
            location: [{
                key: 'Location',
                value: 'https://www.openttd.org' + redirect_uri,
            }],
        },
    };
    callback(null, response);
    return;
};
