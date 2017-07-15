# passwd format
# username:passhash:email@address.com

class PasswdParseException(Exception):
    pass

def parse_line(passwd_line):
    parts = passwd_line.split(':')
    
    if not len(parts) == 3:
        raise PasswdParseException('There must be three : separated values')

def parse_fobj(fobj):

    users = {}

    line_no = 1

    for line in fobj.readline():
        try:
            username, passwd_hash, email = parse_line(line)
            users[username] = {
                'passwd_hash': passwd_hash,
                'email': email
            }
        except Exception as e:
            raise PasswdParseException('Parser error, line #%s - %s' % (line_no, e.message))
    
    return users




def load_passwd_file(passwd_file):

    

    f = open(passwd_file)

    line_no = 1

    users = []

    for line in f.readline():
        try:
            username, passwd_hash, email = parse_line(line)
        except Exception as e:
            raise PasswdParseException('Parser error, line #%s - %s' % (line_no, e.message))

    passwd_file = f.read()




class UserDB():
    def __init__(self, passwd_file, users=None):
        self._passwd_file = passwd_file
        if users == None:
            self._users = {}
        else:
            self._users = users

        self._length = len(self._users.keys())


    def __len__(self):
        return self._length

    def add_user(self, username, passwd_hash, email):
        if username in self._users:
            raise Exception('User %s already exists!' % username)

