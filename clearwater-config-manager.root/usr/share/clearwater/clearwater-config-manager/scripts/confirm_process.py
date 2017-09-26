# Copyright (C) Metaswitch Networks.
"""Module containing a function to ask the user to confirm a process"""


def confirm_yn(prompt):
    """Asks the user to confirm they want to make the changes described by the
    prompt passed in. This keeps asking the user until a valid response is
    given. True or false is returned for a yes no input respectively"""
    question = "Do you want to continue?  [yes/no] "

    while True:
        print '\n{0} '.format(prompt)
        supplied_input = raw_input(question)
        if supplied_input.strip().lower() not in ['y', 'yes', 'n', 'no']:
                print '\n Answer must be yes or no'
        else:
            return supplied_input.strip().lower().startswith('y')


