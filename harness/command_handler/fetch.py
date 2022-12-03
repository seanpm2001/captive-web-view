# Run with Python 3
"""\
HTTP server that can be used as a back end. This server is based on the HTTP
back end to Local WebView applications.

Run it like:

    cd /path/where/you/cloned/cwvpiv/
    python3 ./httpBridge/cwvpiv.py
"""
#
# Standard library imports, in alphabetic order.
# Module for HTTP server, not imported here but handy to have the link.
# https://docs.python.org/3/library/http.server.html
#
# Module for Base 64 encoding certificate DER data.
# https://docs.python.org/3/library/base64.html
import base64
#
# Cryptographic hash module. Only used to generate a certificate thumbprint.
# https://docs.python.org/3/library/hashlib.html
import hashlib


from http.client import HTTPSConnection


#
# JSON module.
# https://docs.python.org/3/library/json.html
import json
#
# Module for OO path handling.
# https://docs.python.org/3/library/pathlib.html
from pathlib import Path
#
# Module for socket connections. Only used to generate a wrap-able socket for a
# TLS connection so that the peer certificate can be obtained.
# https://docs.python.org/3/library/socket.html
import socket
#
# Module for creating an unverified SSL/TLS context.
# Uses the undocumented _create_unverified_context() interface.
# TOTH https://stackoverflow.com/a/50949266/7657675
import ssl
#
# Module for spawning a process to run a command.
# https://docs.python.org/3/library/subprocess.html
import subprocess
#
# Module for manipulation of the import path.
# https://docs.python.org/3/library/sys.html#sys.path
import sys
#
# Temporary file module.
# https://docs.python.org/3/library/tempfile.html
from tempfile import NamedTemporaryFile
#
# Module for HTTP errors.
# https://docs.python.org/3/library/urllib.error.html
import urllib.error
#
# Module for URL requests.
# https://docs.python.org/3/library/urllib.request.html
import urllib.request
#
# Local Imports.
#
# Command handler base class.
from .base import CommandHandler

class Fetcher:
    _rootPath = Path().resolve().root
    # TOTH macOS `security` CLI and how to export the system CA stores:
    # https://stackoverflow.com/a/72053605/7657675
    _keychains = (
        (
            _rootPath, 'System', 'Library', 'Keychains'
            , 'SystemRootCertificates.keychain'
        ), (
            _rootPath, 'Library', 'Keychains', 'System.keychain'
        )
    )

    def __init__(self):
        self._pemPath = self.keychain_PEM()

        # Create a context in which the certificates from the keychain will be
        # used to verify the host.
        self._sslContext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._sslContext.load_verify_locations(self._pemPath)

        # Note that host verification has to be switched on here for the peer
        # certificate to be available later, when the secure socket is
        # connected. Also, the host certificate has to be valid. For later
        # maybe, use something from this SO answer to get the certificate even
        # if it isn't valid.
        # https://stackoverflow.com/a/7691293/7657675

        # The sslContext no longer requires the PEM file but it's used later by
        # the openssl s_client.
        # self._pemPath.unlink()

    def keychain_PEM(self):
        # Export all the certificates from the system keychains into a single
        # temporary PEM file. Return the Path of the file.
        #
        # TOTH macOS `security` CLI and how to export the system CA stores:
        # https://stackoverflow.com/a/72053605/7657675
        #
        # TOTH creating a temporary file instead of loading it in the bash
        # profile:  
        # https://stackoverflow.com/a/70054211/7657675
        with NamedTemporaryFile(mode='w', delete=False, suffix=".pem") as file:
            pemPath = Path(file.name)

        for keychain in self._keychains:
            keychainPath = Path(*keychain)
            # TOTH macOS `security` CLI and how to export the system CA stores:
            # https://stackoverflow.com/a/72053605/7657675
            securityRun = subprocess.run(
                (
                    'security', 'export', '-k', keychainPath, '-t', 'certs'
                    , '-f', 'pemseq'
                ), stdout=subprocess.PIPE, text=True
            )
            print(f'"{keychainPath}" PEM {len(securityRun.stdout)} characters.')
            with pemPath.open('a') as file:
                file.write(securityRun.stdout)

        certificates = 0
        with pemPath.open() as file:
            while True:
                line = file.readline()
                if line == '':
                    break
                if line.startswith('--') and 'BEGIN CERTIFICATE' in line:
                    certificates += 1
        print(f'Keychain certificates: {certificates}.')

        return pemPath

# Returns a 404 and empty body.
# https://httpbin.org/status/404
#
# Returns a JSON object.
# https://httpbin.org/get
#
# Returns a 400 and error message in HTML.
# https://client.badssl.com/


    def fetch(self, parameters, httpHandler=None):
        peerCertEncoded = None
        peerCertLength = None
        fetchedRaw = None

        def return_(status, fetched, details):
            return_ = {
                "peerCertificateDER": peerCertEncoded,
                "peerCertificateLength": peerCertLength,
                'fetchedRaw': fetchedRaw
            }
            if fetched is None:
                return_['fetchError'] = details
                if status is not None:
                    return_['fetchError']['status'] = status
            else:
                return_['fetched'] = fetched
                return_['fetchedDetails'] = details
                if status is not None:
                    return_['fetchedDetails']['status'] = status
            return return_

        # resource = parameters['resource']
        # url = urllib.parse.urlparse(resource)
        # host = url.hostname
        # port = 443 if url.port is None else url.port
        url, port, fetchError = self._parse_resource(parameters)
        self._log(httpHandler, f'fetch() {url.hostname} {port}.')
        if fetchError is not None:
            return return_(0, None, fetchError)

        # if url.hostname is None:
        #     return return_(1, None, {
        #         'statusText': "No url.hostname in parameters.resource",
        #         'resource': resource,
        #         'url': f'{url}'
        #     })



        # try:
        #     connection = HTTPSConnection(
        #         url.hostname, port=port, context=self._sslContext)
        # except Exception as error:
        #     return return_(2, None, {
        #         'statusText': f'HTTPSConnection({url.hostname},{port},) {error}'})

        # try:
        #     connection.connect()
        # except Exception as error:
        #     return return_(3, None, {
        #         'statusText': (
        #             f'HTTPSConnection({url.hostname},{port},).connect() {error}')})
        connection, fetchError = self._connect(url.hostname, port)
        if fetchError is not None:
            return return_(1, None, fetchError)

        peerCertEncoded, peerCertLength = self.get_peer_certificate(
            connection, httpHandler)

        fetchedRaw, details = self._request(connection, parameters)
        connection.close()

        if details['status'] >= 400:
            return return_(None, None, details)

        # fetched = self.fetch_JSON(parameters, httpHandler, host, port)
        # peerCertEncoded, peerCertLength = self.get_peer_certificate(
        #     host, port, httpHandler)

        fetchedObject, fetchError = self._parse_JSON(fetchedRaw)
        if fetchError is not None:
            return return_(2, None, fetchError)

        # As an additional manual check, dump the thumbprint with the openssl
        # CLI.
        #
        # url.netloc includes port, if there was one in the URL.
        self.openssl_thumbprint(
            url.hostname
            , f'{url.hostname}:{port}' if url.port is None else url.netloc
            , httpHandler)
        
        return return_(None, fetchedObject, details)

        # return {
        #     **fetched,
        #     "peerCertificateDER": peerCertEncoded,
        #     "peerCertificateLength": peerCertLength
        # }

    def _parse_resource(self, parameters):
        try:
            resource = parameters['resource']
        except KeyError:
            return None, None, {
                'statusText': 'No "resource" in parameters.',
                'parameterKeys': tuple(parameters.keys())
            }

        url = urllib.parse.urlparse(resource)
        # host = url.hostname
        # port = 443 if url.port is None else url.port
        # if url.port is None:
        #     url.port = 443

        if url.hostname is None:
            return None, None, {
                'statusText': "No host in parameters.resource",
                'resource': resource,
                'url': f'{url}'
            }

        return url, 443 if url.port is None else url.port, None

    def _connect(self, host, port):
        try:
            connection = HTTPSConnection(
                host, port=port, context=self._sslContext)
        except Exception as error:
            return None, {
                'statusText': f'HTTPSConnection({host},{port},) {error}'}

        try:
            connection.connect()
        except Exception as error:
            return None, {
                'statusText': (
                    f'HTTPSConnection({host},{port},).connect() {error}')}
        
        return connection, None

    def get_peer_certificate(self, connection, httpHandler):
        # The connection.sock property mightn't be documented but seems safe.
        peerCertBinary = connection.sock.getpeercert(True)
        peerCertDict = connection.sock.getpeercert(False)

        peerCertLength = len(peerCertBinary)
        peerCertMessage = "\n".join([
            f'{key} "{value}"' for key, value in peerCertDict.items()
        ])
        self._log(httpHandler
            , f'Peer certificate. Binary length: {peerCertLength}'
            f'. Dictionary:\n{peerCertMessage}')

        # TOTH Generate fingerprint with openssl and Python:
        # https://stackoverflow.com/q/70781380/7657675
        peerThumb = hashlib.sha1(peerCertBinary).hexdigest()
        self._log(httpHandler, f'Peer certificate thumbprint:\n{peerThumb}')
        # www.python.org SHA1 Fingerprint=B0:9E:C3:40:F4:19:78:D7:7A:76:84:79:0A:EF:84:0E:AD:DA:49:FD
        # B09EC340F41978D77A7684790AEF840EADDA49FD
        # b09ec340f41978d77a7684790aef840eadda49fd

        return base64.b64encode(peerCertBinary).decode('utf-8'), peerCertLength

    def _request(self, connection, parameters):
        try:
            options = parameters['options']
        except KeyError:
            options = {}

        method = options.get('method')
        connection.putrequest(
            'GET' if method is None else method, parameters['resource'])
            # try None

        # Assume any body is JSON for now.
        if 'body' in options or 'bodyObject' in options:
            connection.putheader('Content-Type', "application/json")

        try:
            for header, value in options['headers'].items():
                connection.putheader(header, value)
        except KeyError:
            pass

            # if 'body' in options:
            #     body = options['body'].encode()
            # elif 'bodyObject' in options:
            #     body = json.dumps(options['bodyObject']).encode()
            # else:
            #     body = None

        connection.endheaders(
            options['body'].encode() if 'body' in options else
            json.dumps(options['bodyObject']).encode()
            if 'bodyObject' in options else None
        )
        connection.send(b'')
        response = connection.getresponse()

        # https://docs.python.org/3/library/http.client.html#httpresponse-objects

        return response.read().decode('utf-8'), {
            'status': response.status,
            'statusText': response.reason,
            'headers': dict(response.getheaders())
        }

    def _parse_JSON(self, raw):
        if raw is None or len(raw) == 0:
            return raw, None

        try:
            return json.loads(raw), None

        except json.decoder.JSONDecodeError as error:
            # https://docs.python.org/3/library/json.html#json.JSONDecodeError
            return None, {
                'statusText': 'JSONDecodeError',
                'headers': {
                    'msg':error.msg,
                    'lineno': error.lineno, 'colno': error.colno
                }
            }

    def fetch_JSON(self, parameters, httpHandler, host, port):
        # Fetch the resource in the context. ToDo:
        #
        # -   Make it handle different encoding schemes instead of assuming
        #     utf-8.

        request = urllib.request.Request(parameters['resource'])

        if 'options' in parameters:
            options = parameters['options']
            if 'method' in options:
                request.method = options['method']
            if 'body' in options:
                request.data = options['body'].encode()
                # Assume it's JSON.
                request.add_header('Content-Type', "application/json")
            if 'bodyObject' in options:
                request.data = json.dumps(options['bodyObject']).encode()
                request.add_header('Content-Type', "application/json")
            if 'headers' in options:
                for header, value in options['headers'].items():
                    request.add_header(header, value)

        self._log(
            httpHandler,
            f'Request:\nhost "{request.host}"\nBody: {request.data}'
            f'\nselector "{request.selector}"'
            f'\nheaders {request.header_items()}'
        )

        opened = None
        details = None
        try:
            # opened = urllib.request.urlopen(request, context=self._sslContext)
            connection = HTTPSConnection(
                host, port=port, context=self._sslContext
            )
            self._log(httpHandler, f'{connection.sock} {dir(connection)}')

            connection.connect()
            self._log(httpHandler, f'{connection.sock} {dir(connection)}')

            sslSocket = connection.sock
            peerCertBinary = sslSocket.getpeercert(True)
            peerCertDict = sslSocket.getpeercert(False)
            self._log(httpHandler, f'{peerCertDict}')



            opened = None

            connection.close()
            details = {
                # 'opened': True,
                # 'status': opened.status,
                # 'statusText': opened.msg,
                # 'headers': dict(opened.headers.items())
            }
        except urllib.error.HTTPError as error:
            details = {
                'opened': False,
                'status': error.code,
                'statusText': error.reason,
                'headers': dict(error.headers.items())
            }
        self._log(httpHandler, f'Opened details: {details}')

        raw = None if opened is None else opened.read().decode('utf-8')
        fetchedLength = None if raw is None else len(raw)
        self._log(httpHandler, f'Fetched length: {fetchedLength}.')

        if details['status'] >= 400:
            return {'fetchError': details, 'fetchedRaw': raw}



        try:
            return {
                'fetched': (
                    None if raw is None or len(raw) == 0 else json.loads(raw)),
                'fetchedDetails': details,
                'fetchedRaw': raw
            }
        except json.decoder.JSONDecodeError as error:
            return {
                #f'JSONDecodeError {error}',
                # https://docs.python.org/3/library/json.html#json.JSONDecodeError
                'fetchError': {
                    'status': 0,
                    'statusText': error.msg,
                    'headers': { 'lineno': error.lineno, 'colno': error.colno }
                },
                'fetchedRaw': raw
            }
    
    def openssl_thumbprint(self, serverName, connectAddress, httpHandler):
        # TOTH Generate fingerprint with openssl and Python:
        # https://stackoverflow.com/q/70781380/7657675
        #
        # TOTH Terminate openssl client:
        # https://stackoverflow.com/a/34749879/7657675
        #
        # See also the MS documentation about thumbprint
        # https://docs.microsoft.com/en-us/dotnet/api/system.security.cryptography.x509certificates.x509certificate2.thumbprint?view=net-6.0#system-security-cryptography-x509certificates-x509certificate2-thumbprint

        # First run the openssl CLI to connect to the server. This logs the peer
        # certificate, and more besides.
        s_clientRun = subprocess.run(
            (
                'openssl', 's_client', '-servername', serverName, '-showcerts'
                , '-CAfile', str(self._pemPath), '-connect', connectAddress
            ), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE
            , stderr=subprocess.PIPE, text=True
        )
        self._log(httpHandler, f'openssl s_client stderr\n{s_clientRun.stderr}')

        # Extract the PEM dump of the peer certificate from the s_client output.
        s_clientCertificatePEM = None
        for line in s_clientRun.stdout.splitlines(True):
            if line.startswith('--') and 'BEGIN CERTIFICATE' in line:
                s_clientCertificatePEM = []
            if s_clientCertificatePEM is not None:
                s_clientCertificatePEM.append(line)
            if line.startswith('--') and 'END CERTIFICATE' in line:
                break
        self._log(httpHandler
            , f'openssl s_client PEM lines: {len(s_clientCertificatePEM)}')

        # Pipe the PEM back into the openssl x509 CLI and have it calculate the
        # thumbprint aka fingerprint.
        x509Run = subprocess.run(
            ('openssl', 'x509', '-inform', 'PEM', '-fingerprint', '-noout')
            , input=''.join(s_clientCertificatePEM)
            , stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        self._log(httpHandler, f'openssl x509\n{x509Run.stdout}')

    def _log(self, httpHandler, message):
        if httpHandler is None:
            print(message)
        else:
            httpHandler.log_message("%s", message)
    
class FetchCommandHandler(CommandHandler):
    def __init__(self):
        self._fetcher = Fetcher()
        super().__init__()

    # Override.
    def __call__(self, commandObject, httpHandler):
        command, parameters = self.parseCommandObject(commandObject)

        if command != 'fetch':
            return None

        return self._fetcher.fetch(parameters, httpHandler)