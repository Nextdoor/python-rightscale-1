"""
Python-Rightscale

A stupid wrapper around rightscale's HTTP API
"""
from functools import partial
import requests


class RESTOAuthClient(object):
    """
    HTTP client that is aware of REST and OAuth semantics.
    """
    def __init__(self):
        self.endpoint = ''
        self.headers = {}

        # convenience methods
        self.get = partial(self.request, 'get')
        self.post = partial(self.request, 'post')

    def request(self, method, path='/', url=None, ignore_codes=[], **kwargs):
        """
        Performs HTTP request.

        :param str method: An HTTP method (e.g. 'get', 'post', 'PUT', etc...)

        :param str path: A path component of the target URL.  This will be
            appended to the value of ``self.endpoint``.  If both :attr:`path`
            and :attr:`url` are specified, the value in :attr:`url` is used and
            the :attr:`path` is ignored.

        :param str url: The target URL (e.g.  ``http://server.tld/somepath/``).
            If both :attr:`path` and :attr:`url` are specified, the value in
            :attr:`url` is used and the :attr:`path` is ignored.

        :param list of int ignore_codes: List of HTTP error codes (e.g.
            404, 500) that should be ignored.  If an HTTP error occurs and it
            is *not* in :attr:`ignore_codes`, then an exception is raised.

        :param kwargs: Any other kwargs to pass to :meth:`requests.request()`.

        Returns a :class:`requests.Response` object.
        """
        _url = url if url else (self.endpoint + path)

        # merge with defaults in headers attribute.  incoming 'headers' take
        # priority over values in self.headers to allow last-minute overrides
        # if the caller really knows what they're doing.
        if 'headers' in kwargs:
            headers = kwargs.pop('headers')
            for k, v in self.headers.items():
                headers.setdefaults(k, v)
        else:
            headers = self.headers
        kwargs['headers'] = headers

        r = requests.request(method, _url, **kwargs)
        if not r.ok and r.status_code not in ignore_codes:
            r.raise_for_status()
        return r


class RightScale(RESTOAuthClient):
    def __init__(
            self,
            account,
            refresh_token,
            api_endpoint='my',
            oauth_endpoint='us-3',
            cloud_id='1'
            ):
        """
        Creates and configures the API object.
        :param account: The Rightscale account number
        :param refresh_token: The refresh token provided by Rightscale when API
            access is enabled.
        :param api_endpoint: The rightscale subdomain to be hit with API
            requests.  Defaults to 'my'.
        :param oauth_endpoint: The rightscale subdomain to be hit with OAuth
            token requests.  Defaults to 'us-3'.
        """
        super(RightScale, self).__init__()
        self.headers['X-API-Version'] = '1.5'
        self.endpoint = 'https://%s.rightscale.com/api/' % api_endpoint

        self.account = account
        self.oauth_url = (
                'https://%s.rightscale.com/api/oauth2/'
                % oauth_endpoint
                )
        self.refresh_token = refresh_token
        self.auth_token = None
        self.cloud_id = cloud_id

    def login(self):
        """
        Gets and stores an OAUTH token from Rightscale.
        """
        login_data = {
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
                }
        response = self.post(url=self.oauth_url, data=login_data)

        if response.ok:
            raw_token = response.json()
            self.auth_token = "Bearer %s" % raw_token['access_token']
            self.headers['Authorization'] = self.auth_token
            return True

        return False

    def run_script(self, server_id, script_id, inputs=None):
        """
        Convenience function to run a rightscript on a single server and verify
        its status.

        :param server_id: the Rightscale server id taken from the url of the
            server
        :param script_id: the id of the Rightscript to run on the server, taken
            from the url of the rightscript
        :param inputs (optional): a dict of the inputs to pass to the
            rightscript, in the format 'INPUT NAME': 'text:Value'
        """
        api_request = 'cloud/%s/instances/%s/run_executable' % (
                self.cloud_id,
                server_id,
                )
        script_href = '/api/right_script/%s' % (script_id)
        payload = {'right_script_href': script_href}
        input_list = []
        if inputs:
            for key in inputs:
                input_list.append('[name]=' + key)
            input_list.append('[value]' + inputs[key])
            payload['inputs[]'] = input_list
        response = self.post(api_request, payload)
        return response

    def list_instances(self, deployment=None):
        """
        Returns a list of instances from your account.

        :param deployment (optional): If provided, only lists servers in the
            specified deployment
        """
        filters = ['state==operational']
        if deployment:
            filters.append(
                    'deployment_href==/api/deployments/' + deployment
                    )
        params = {'filter[]': filters}
        api_request = 'clouds/%s/instances' % self.cloud_id
        response = self.get(api_request, params=params)
        # TODO: return something more meaningful once we know what format it
        # comes back in.
        return response
        # instance_list = {}
        # for svr in response:
        #     instance_list[svr['resource_uid']] = svr
        # return instance_list
