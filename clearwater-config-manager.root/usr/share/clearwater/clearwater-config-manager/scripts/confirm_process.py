
# Copyright (C) Metaswitch Networks.
"""Script to ask the user to confirm a process"""


def Confirm_yn(prompt):
    """asks the user to confirm they want to make the changes described by the
    prompt passed in. This keeps asking the user until a valid response is
    given."""
    question = "Do you want to continue?"
    allowed = False
    while allowed is False:
        print '\n{0} '.format(prompt)
        supplied_input = raw_input('{0} [yes/no] '.format(question))
        try:
            if supplied_input.strip().lower() not in ['y', 'yes', 'n', 'no']:
                raise ValueError('Answer must be yes or no')
            else:
                response = supplied_input.lower().startswith('y')
                allowed = True
        except ValueError as exc:
            print("\n" + str(exc))

    return response
