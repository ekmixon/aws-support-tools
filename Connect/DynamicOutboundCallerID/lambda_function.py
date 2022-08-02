'''
Copyright 2018-2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file
except in compliance with the License. A copy of the License is located at

    http://aws.amazon.com/apache2.0/

or in the "license" file accompanying this file. This file is distributed on an "AS IS"
BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
License for the specific language governing permissions and limitations under the License.
'''

import logging
import phonenumbers
import botocore
import boto3
import os
import json
import re
logger = logging.getLogger()
# Logging level can be changed between logging.INFO to logging.ERROR to show verbose information or errors only in CloudWatch
logger.setLevel(logging.ERROR)
s3 = boto3.resource("s3")
e164_format = re.compile("^\+?[1-9]\d{1,14}$")

def lambda_handler(event, context):
    try:
        customer_no = event["Details"]["ContactData"]["CustomerEndpoint"]["Address"]
        if e164_format.match(customer_no) == False:
            raise Exception(
                "Is it a valid phone number?")
        customer_country = phonenumbers.phonenumberutil.region_code_for_country_code(
            phonenumbers.parse(customer_no).country_code)
    except Exception:
        logger.error(
            "Cannot retrieve Details.ContactData.CustomerEndpoint.Address from Amazon Connect. Is the parameter parsed by Amazon Connect?")
        return None
    try:
        default_queue_outbound_no = event["Details"]["ContactData"]["Queue"]["OutboundCallerId"]["Address"]
        default_queue_outbound_country = phonenumbers.phonenumberutil.region_code_for_country_code(
            phonenumbers.parse(default_queue_outbound_no).country_code)
    except Exception:
        logger.error(
            "Cannot retrieve Details.ContactData.Queue.OutboundCallerId.Address from Amazon Connect. Is the parameter parsed by Amazon Connect?")
        return None
    try:
        if(os.environ["BUCKET_NAME"] == ""):
            raise KeyError("BUCKET_NAME")
        if(os.environ["COUNTRY_ROUTING_LIST_KEY"] == ""):
            raise KeyError("COUNTRY_ROUTING_LIST_KEY")
        logger.info(
            f'Bucket: {os.environ["BUCKET_NAME"]} Key: {os.environ["COUNTRY_ROUTING_LIST_KEY"]}'
        )

    except KeyError as err:
        if(str(err) == "\'BUCKET_NAME\'"):
            logger.error(
                "Cannot read the environment variable \"BUCKET_NAME\". Have you set it up properly?")
        if(str(err) == "\'COUNTRY_ROUTING_LIST_KEY\'"):
            logger.error(
                "Cannot read the environment variable \"COUNTRY_ROUTING_LIST_KEY\". Have you set it up properly?")
        logger.error(
            f"Assigning the default outbound number ({default_queue_outbound_no}) from {default_queue_outbound_country} for the queue as the outbound number."
        )

        response = {
            "customer_number": customer_no,
            "customer_country": customer_country,
            "outbound_number": default_queue_outbound_no,
            "outbound_country": default_queue_outbound_country,
            "default_queue_outbound_number": default_queue_outbound_no,
            "default_queue_outbound_country": default_queue_outbound_country
        }
        numObj = phonenumbers.parse(response["outbound_number"])
        if not phonenumbers.is_valid_number(numObj) and e164_format.match(response["outbound_number"]) == False:
            logger.error(f'Outbound number {response["outbound_number"]} is not valid.')
            return None
        return response
    try:
        logger.info(
            f'Attempt to get country routing list \"{os.environ["COUNTRY_ROUTING_LIST_KEY"]}\" from bucket \"{os.environ["BUCKET_NAME"]}\".'
        )

        country_routing_list = json.loads(s3.Object(
            os.environ["BUCKET_NAME"], os.environ["COUNTRY_ROUTING_LIST_KEY"]).get()["Body"].read().decode("utf-8"))
        logger.info("Download completed.")
    except botocore.exceptions.ClientError:
        logger.error(
            f'Cannot access bucket \"{os.environ["BUCKET_NAME"]}\" and key \"{os.environ["COUNTRY_ROUTING_LIST_KEY"]}\". Does the Lambda function have relevant permissions? Does the S3 bucket and/or object exist?'
        )

        return None
    except Exception as err:
        logger.error(
            f'Cannot get country routing list from S3 bucket \"{os.environ["BUCKET_NAME"]}\" with key \"{os.environ["COUNTRY_ROUTING_LIST_KEY"]}\".\nError: {err}'
        )

        return None
    if customer_country in country_routing_list:
        try:
            outbound_no = country_routing_list[customer_country]
            outbound_country = phonenumbers.phonenumberutil.region_code_for_country_code(
                phonenumbers.parse(outbound_no).country_code)
            logger.info(
                f"Country {customer_country} have set up an outbound number. Assigning the number ({outbound_no}) from {outbound_country} as the outbound number."
            )

        except Exception:
            logger.error(
                f'Cannot parse the default number in the country routing list file. Does the value for key \"{customer_country}\" exist?'
            )

            logger.error(
                f"Assigning the number set for the default queue ({default_queue_outbound_no}) as the outbound number."
            )

            outbound_no = default_queue_outbound_no
            outbound_country = default_queue_outbound_country
    else:
        try:
            outbound_no = country_routing_list["Default"]
            outbound_country = phonenumbers.phonenumberutil.region_code_for_country_code(
                phonenumbers.parse(outbound_no).country_code)
            logger.info(
                f"Country {customer_country} have not set up an outbound number. Assigning the Default number ({outbound_no}) from {outbound_country} as the outbound number."
            )

        except Exception:
            logger.error(
                "Cannot parse the default number in the country routing list file. Does the value for/or key \"Default\" exist?")
            logger.error(
                f"Assigning the number set for the default queue ({default_queue_outbound_no}) as the outbound number."
            )

            outbound_no = default_queue_outbound_no
            outbound_country = default_queue_outbound_country
    response = {
        "customer_number": customer_no,
        "customer_country": customer_country,
        "outbound_number": outbound_no,
        "outbound_country": outbound_country,
        "default_queue_outbound_number": default_queue_outbound_no,
        "default_queue_outbound_country": default_queue_outbound_country
    }
    numObj = phonenumbers.parse(response["outbound_number"])
    if not phonenumbers.is_valid_number(numObj) and e164_format.match(response["outbound_number"]) == False:
        logger.error(f'Outbound number {response["outbound_number"]} is not valid.')
        return None
    if (outbound_no != default_queue_outbound_no):
        logger.info(
            f"If the outbound number ({outbound_no}) is not claimed in your Amazon Connect instance, the number set for the default queue will be used ({default_queue_outbound_no})."
        )

    return response
