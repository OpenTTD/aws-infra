'use strict';

exports.handler = (event, context, callback) => {
    var request = event.Records[0].cf.request;
    var olduri = request.uri;

    // Rewrite the first to the second:
    //   base-graphics/12345678/12345678901234567890123456789012/filename.tar.gz
    //   base-graphics/12345678/12345678901234567890123456789012.tar.gz
    // This allows the OpenTTD client to know the name to use for the file,
    //   while the S3 only knows the md5sum based name.
    var newuri = olduri.replace(/^\/([a-z-]+)\/([a-f0-9]{8})\/([a-f0-9]{32})\/[a-zA-Z0-9-_\.]+.tar.gz$/, '\/$1\/$2\/$3.tar.gz');
    request.uri = newuri;

    return callback(null, request);
};
