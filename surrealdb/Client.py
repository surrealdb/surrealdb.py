import urllib3
import base64
import json
import time
import sys

class client:
    def __init__(self, host, user, password, ns, db):
        auth_header = base64.b64encode((user + ':' + password).encode('utf-8'))
        self.hosts = [host + '/sql', auth_header, ns, db]
        self.headers = {'Content-Type': 'application/json', 'NS': self.hosts[2], 'DB': self.hosts[3], 'Accept': '*/*', 'Accept-Encoding': 'gzip, deflate, br', 'Connection': 'keep-alive', 'User-Agent': 'SurrealDB.py/1.0', 'Authorization': 'Basic ' + self.hosts[1].decode('utf-8')}
        self.http = urllib3.PoolManager()
        # Put the client into the pool
        r = self.http.request('GET', self.hosts[0], headers=self.headers)
    def execute(self, query):        
        r = self.http.request('POST', self.hosts[0], headers=self.headers, body=query.encode('utf-8'))
        return r.data.decode('utf-8')
    def startTx(self):
        r = self.http.request('POST', self.hosts[0], headers=self.headers, body='START TRANSACTION;'.encode('utf-8'))
        return "Transaction started."
    def commit(self):
        r = self.http.request('POST', self.hosts[0], headers=self.headers, body='COMMIT;'.encode('utf-8'))
        return "Transaction committed."