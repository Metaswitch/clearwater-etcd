# adjusted stats engine case from testing.py to drop some functions and
# make this just a yes/no case and with the asking


def Confirm_yn(prompt):
    """asks the user to confirm they want to make the changes described
    by the prompt passed in"""
    question = "Do you want to continue?"
    allowed = False
    while allowed is False:
        print '\n{0} '.format(prompt)
        supplied_input = raw_input('{0} [yes/no] '.format(question))
        try:
            if supplied_input.strip().lower() not in ['y', 'yes', 'n', 'no']:
                raise ValueError('Answer must be yes or no')
            else:
                reply = supplied_input.lower().startswith('y')
                allowed = True
        except ValueError as exc:
            print("\n" + str(exc))

    print reply
    return reply

if __name__ == "__main__":
    Confirm_yn('Shared configuration is ready to be uploaded')
