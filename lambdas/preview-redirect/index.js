'use strict';

exports.handler = (event, context, callback) => {
    var request = event.Records[0].cf.request;
    var olduri = request.uri;

    var newuri = olduri.replace(/^\/([\w-]+)\/$/, '\/$1\/openttd.html');
    request.uri = newuri;

    return callback(null, request);
};
