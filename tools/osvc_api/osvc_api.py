import os

from dotenv import load_dotenv

load_dotenv()  # OSVC_USERNAME / OSVC_PASSWORD from .env
#!/usr/bin/env python
# coding: utf-8

# In[1]:


import requests
from requests.auth import HTTPBasicAuth


# In[2]:


from datetime import datetime, timedelta, date, time, tzinfo
class UTC(tzinfo):
    """UTC"""

    def __init__(self):
        pass

    def utcoffset(self, dt):
        return timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return timedelta(0)

utc = UTC()


# In[48]:


class OsvcAccessException(Exception):
    pass

class OsvcDataException(Exception):
    pass

"""
Used to interact with the OSvC REST API

The OsvcRequest class sets up some shared details across the functions
and performs HTTP requests to different endpoints.
https://docs.oracle.com/en/cloud/saas/b2c-service/20a/

Example Usage:
    osvc = OsvcRequest(url='service.elsevier.com', username='foo', password='bar')
    res = osvc.get_incident(31234567)
    report_res = osvc.fetch_report(1234)
"""
import json
import logging

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class OsvcRequest:
    """
    Used to interact with the OSvC REST API

    Attributes:
        **kwargs:
            url: OSvC domain, e.g. test site vs. live site
            username: valid OSvC username
            password: valid OSvC password
            limit: OSvC report total count limit.
    """

    def __init__(self, **kwargs):
        self.cols = []
        self.rows = []
        self.url = kwargs.get('url', '') + "services/rest/connect/v1.4/"
        self.user = kwargs.get('username', '')
        self.password = kwargs.get('password', '')
        self.limit = int(kwargs.get('limit', 10000))
        self.headers = {
            'OSvC-CREST-Application-Context': 'Retrieve Data',
            'Content-Type': 'application/json'
        }

        self.report_total_count = 0
        self.report_name = ""
        self.offset = 0
        self.might_have_more = True

    def reset(self):
        """
        Used to reset class variables

        When doing multiple reports with the same class,
        it will reset the variables used for report fetching.

        Returns:
            None
        """
        self.cols = []
        self.rows = []
        self.offset = 0
        self.report_total_count = 0
        self.report_name = ""

    def fetch_report(self, report_id, filters=None):
        """
        Used to set up and execute an OSvC report.

        Sets up filters, columns, then runs the report.

        Args:
            - report_id: unique identifier of the report
            - filters: OSvC report filters.
        Returns:
            Returns an array which contains python dicts of each row
            pulled from the API. If API call failed, returns None
        """
        
        if filters is None:
            filters = []

        # Reset cols / rows variable
        self.reset()

        report_request = {
            "id": report_id,
            "limit": self.limit,
            "offset": self.offset,
            "filters": filters
        }
        
        try:
            status = self.get_report(report_request)
        except Exception as e:
            raise e

        if status:
            return self.rows
        else:
            return None

    def get_report(self, data):
        """
        Makes a POST request to run an OSvC report.

        Sets POST request headers, authentication and data to send,
        then handles the response.

        Args:
            - data: a python dictionary, containing the report metadata.
        Returns:
            False on failure
            True on success
        """
        logger.debug("Processing a call for %s", data)

        try:
            response = requests.post(
                self.url + "analyticsReportResults",
                data=json.dumps(data),
                auth=HTTPBasicAuth(self.user, self.password),
                headers=self.headers
            )
        except Exception as e:
            raise e
        
        report = response.json()
        
        if "status" in report and report["status"] != 200:
            if report['status'] == 401:
                raise OsvcAccessException(report['detail'])
            elif report['status'] == 400:
                raise OsvcDataException(report['detail'])
            else:
                raise RuntimeError(report["detail"])

        self.report_total_count += len(report["rows"])
        self.offset += len(report["rows"])
        self.report_name = report["name"]
        self.might_have_more = (len(report["rows"]) == self.limit)

        self.handle_response(report)

        if self.might_have_more:
            data["offset"] = self.offset
            self.get_report(data)

        return True

    def handle_response(self, response):
        """
        Saves an OSvC response as class vars.

        Saves the rows and column names from the response object.

        Args:
            - response: OSvC response object.
        Returns:
            None
        """

        self.get_column_headers(response['columnNames'])
        self.get_rows(response['rows'])

    def get_column_headers(self, column_names):
        """
        Saves an OSvC response column names.

        Args:
            - response: column_names: an array containing
            the columns retrieved from an OSvC request.
        Returns:
            None
        """

        self.cols = column_names

    def get_rows(self, rows):
        """
        Extracts row data from an OSvC response.

        Uses the column names to loop over the rows
        and add to a class array.

        Args:
            - rows: an array containing OSvC report rows.
        Returns:
            None
        """

        for row in rows:
            new_row = {}
            for i, val in enumerate(row):
                new_row[self.cols[i]] = val
            self.rows.append(new_row)


# In[49]:


osvc_username = os.environ["OSVC_USERNAME"]
osvc_password = os.environ["OSVC_PASSWORD"]

osvc = OsvcRequest(url="https://service.elsevier.com/", username=osvc_username, password=osvc_password)


# In[50]:

# For the chat one, you change the report_id from 166278 to 166280

report_id = 166278
product_id = ['2.18847']
# product_id = ['2.10955', '2.10968'] #consult
# product_id = ['2.10886', '2.18116', '2.10891', '2.10892', '2.17995', '2.10893', '2.10894', '2.10895', '2.10888', '2.10896', '2.10897', '2.15655'] #evolve
# product_id = ['2.10849', '2.13471', '2.10850', '2.10855', '2.10852', '2.10856', '2.13458', '2.10857', '2.16231', '2.16954', '2.17035', '2.17036', '2.17059', '2.15920', '2.16142'] #clinicalkey
# 10955 consult
# 10968 ebooks+
# 2.18130 - CK AI
# 2.18847 - leapspace

# In[51]:


last_run = False
start_date = datetime.combine(date(2025,1,1), time(0, 0, 0), tzinfo=utc)
end_date = datetime.combine(date(2026,5,31), time(23, 59, 59), tzinfo=utc)

request_end_date = start_date + timedelta(hours=24)

data = []
while True:
    if start_date > end_date:
        break
        
    result = osvc.fetch_report(int(report_id), [
        {
            "name":   'incidents.closed',
            "values": [start_date.isoformat(), request_end_date.isoformat()]
        },
        {
            "name":     'incidents.prod_hierarchy',
            "values":   product_id,
            "operator": { "id": 10 }
        }        
    ])
        
    data = data + result

    if last_run:
        break

    start_date = request_end_date
    request_end_date = request_end_date + timedelta(hours=24)
    if request_end_date > end_date:
        request_end_date = end_date
        last_run = True

# print(data)

import pandas as pd
df = pd.DataFrame(data)
df.to_csv('data/leapspace.csv', index=False)
