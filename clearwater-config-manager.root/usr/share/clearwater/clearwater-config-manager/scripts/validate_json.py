# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import jsonschema
import json
import sys
import yaml

# Parse the command line options
if len(sys.argv) != 3:
    print "Usage: validate_json_config <schema to validate against> <file to validate>"
    sys.exit(1)

schema_file = sys.argv[1]
config_file = sys.argv[2]

# Load the schema and config files
try:
    schema = json.load(open(schema_file))
except IOError:
    print "Unable to open {}".format(schema_file)
    sys.exit(1)
except ValueError as e:
    print "{} is not valid.".format(schema_file)
    print "The errors, and the location of the errors in the schema file, are displayed below:\n"
    print e.message
    sys.exit(1)

try:
    config = json.load(open(config_file))
except IOError:
    print "Unable to open {}".format(config_file)
    sys.exit(1)
except ValueError as e:
    print "{} is not valid.".format(config_file)
    print "The errors, and the location of the errors in the configuration file, are displayed below:\n"
    print e.message
    sys.exit(1)

# Validate the configuration file against the schema
validator = jsonschema.Draft4Validator(schema)
error_list=sorted(validator.iter_errors(config), key=lambda e: e.path)

# If there are any errors, we want to print them out in a user friendly fashion,
# then exit with a failure code.

# For each error, we have a deque that tells us where in the file the error is,
# and a string that holds the actual error message, e.g.:
#   "deque([u'hostnames', 0, u'records', u'target'])"
#   "1 is not of type u'string'"
#
# We want to turn this into a list that maps the structure of the JSON file,
# e.g.:
#
# hostnames:
#   element 1:
#     The errors are:
#     - Additional properties are not allowed ('name2' was unexpected)
#     name:
#       The errors are:
#       - 1 is not of type 'string'
#     records:
#       rrtype:
#         The errors are:
#         - 'CNAME2' does not match '^CNAME$'
#       target:
#         The errors are:
#         - 1 is not of type 'string'
#
# We construct a nested dictionary of the errors, then print it out in a YAML
# format.
if error_list:
    print "{} is not valid.".format(config_file)
    print "The errors, and the location of the errors in the configuration file, are displayed below:\n"

    temp_dict = {}
    for error in error_list:
        nest = temp_dict

        # Treat the first entry differently, as this is the key we'll use to
        # actually set the error messages in the dictionary
        if len(error.path) == 0:
            last = "Top level"
        else:
            last = error.path.pop()

        if isinstance(last, int):
            last = 'element %i' % (last + 1)

        for error_part in error.path:
            if isinstance(error_part, int):
                error_part = 'element %i' % (error_part + 1)

            nest = nest.setdefault(str(error_part), {})

        nest.setdefault(str(last), {}).setdefault('The errors are', []).append(error.message)

    print(yaml.dump(temp_dict, default_flow_style=False).replace("u'", "'"))
    sys.exit(1)
