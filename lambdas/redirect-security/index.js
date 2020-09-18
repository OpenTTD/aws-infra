'use strict';

exports.handler = (event, context, callback) => {
    var request = event.Records[0].cf.request;
    var olduri = request.uri;

    var redirecturi;

    if (olduri == "/" || olduri == "/en" || olduri == "/en/") {
        redirecturi = '/security.html';
    } else if (/^\/en\/CVE/.test(olduri)) {
        redirecturi = olduri.replace(/^\/en\/CVE-([0-9]+)-([0-9]+)$/, '\/security\/CVE-$1-$2.html');
    } else if (/^\/CVE/.test(olduri)) {
        redirecturi = olduri.replace(/^\/CVE-([0-9]+)-([0-9]+)$/, '\/security\/CVE-$1-$2.html');
    } else {
        redirecturi = '/security.html';
    }

    const response = {
        status: '301',
        statusDescription: 'Moved Permanently',
        headers: {
            location: [{
                key: 'Location',
                value: 'https://www.openttd.org' + redirecturi,
            }],
        },
    };
    callback(null, response);
    return;
};
