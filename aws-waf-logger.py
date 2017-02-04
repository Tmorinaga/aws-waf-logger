import dateutil.parser
import datetime
import json
import ast
import boto3
import os

def match_web_acl_name(webACL, webACLName):
 id = webACL['WebACLs'][0]['WebACLId']
 name = webACL['WebACLs'][0]['Name'].replace('-', '')

 if webACLName == name:
  return id
 else:
  return ""

def match_rule_name(rule, ruleName):
 id = rule['Rules'][0]['RuleId']
 name = rule['Rules'][0]['Name'].replace('-', '').replace(' ', '')

 if ruleName == name:
  return id
 else:
  return ""

def support_datetime_default(o):
    if isinstance(o, datetime.datetime):
        return o.isoformat()
    raise TypeError(repr(o) + " is not JSON serializable")

def lambda_handler(event, context):
 # Const
 BUCKETNAME = os.environ['BUCKETNAME']

 # Variable
 timestamp = ""
 webACLName = ""
 WebACLId = ""
 ruleName = ""
 
 sns = json.loads(event['Records'][0]['Sns']['Message'])
 
 timestamp = dateutil.parser.parse(sns['StateChangeTime'])

 for dimension in sns['Trigger']['Dimensions']:
  if dimension['name'] == "WebACL":
   webACLName = dimension['value']
  elif dimension['name'] == "Rule":
   ruleName = dimension['value']

 waf = boto3.client('waf')

 # get Web ACL ID
 webACL = waf.list_web_acls( Limit = 1 )
 WebACLId = match_web_acl_name(webACL, webACLName)
 nextMarker = webACL['NextMarker']

 while True:
  if WebACLId != "":
   break

  webACL = waf.list_web_acls( NextMarker = nextMarker, Limit = 1 )
  WebACLId = match_web_acl_name(webACL, webACLName)

  nextMarker = webACL['NextMarker']
  if webACL['WebACLs'][0]['WebACLId'] == nextMarker:
   break

 if WebACLId == "":
  return { 'result' : 'No web ACL ID error.'}

 # get rule ID
 rule = waf.list_rules( Limit = 1 )
 ruleId = match_rule_name(rule, ruleName)
 nextMarker = rule['NextMarker']

 while True:
  if ruleId != "":
   break

  rule = waf.list_rules( NextMarker = nextMarker, Limit = 1 )
  ruleId = match_rule_name(rule, ruleName)

  nextMarker = rule['NextMarker']
  if rule['Rules'][0]['RuleId'] == nextMarker:
   break

 if ruleId == "":
  return { 'result' : 'No rule ID error.'}

 # get sampled requests
    
 try:
  requests = waf.get_sampled_requests( 
   WebAclId = WebACLId, 
   RuleId = ruleId, 
   TimeWindow={ 'StartTime': timestamp + datetime.timedelta(minutes = -10) ,'EndTime': timestamp },
   MaxItems=100
  )
 except Exception as e:
  print "ERROR:" + str(e)
  return { 'result' : 'get sampled requests error.'}

 fileName = timestamp.strftime("%Y%m%d%H%M%S") + "_" + webACLName + "_" + ruleName + ".json"
 key = timestamp.strftime("%Y") + "/" + timestamp.strftime("%m") + "/" + fileName
 print requests['SampledRequests']

 with open("/tmp/"+fileName, "w") as outfile:
  json.dump(requests['SampledRequests'], outfile, indent = 2, default = support_datetime_default)

 s3 = boto3.client('s3')

 try:
  response = s3.upload_file("/tmp/"+fileName, BUCKETNAME, key )
 except Exception as e:
  print "ERROR:" + str(e)
  return { 'result' : 's3 upload error.'}
  
 print "success"
 return { 'result' : 'success'}
