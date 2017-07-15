import semver

class SemverCompare:
    def __init__(self, obj, *args):
        print('self obj: %s' % obj)
        self.obj = obj

    def __lt__(self, other):
        return semver.compare(self.obj, other.obj) < 0

    def __gt__(self, other):
        return semver.compare(self.obj, other.obj) > 0

    def __eq__(self, other):
        return semver.compare(self.obj, other.obj) == 0

    def __le__(self, other):
        return semver.compare(self.obj, other.obj) <= 0

    def __ge__(self, other):
        return semver.compare(self.obj, other.obj) >= 0
    
    def __ne__(self, other):
        return semver.compare(self.obj, other.obj) != 0

a = ['0.1.0','0.0.1','2.3.1','1.2.6','2.0.1']

b = sorted(a, key=SemverCompare)


print(b)
