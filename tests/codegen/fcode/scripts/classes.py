# pylint: disable=missing-function-docstring, missing-module-docstring, missing-class-docstring

class Point(object):
    def __init__(self : 'Point', x : float, y : float):
        self.x = x
        self.y = y

    def __del__(self : 'Point'):
        pass

    def translate(self : 'Point', a : float, b : float):
        self.x = self.x + a
        self.y = self.y + b

p = Point(0.0, 0.0)
x=p.x
p.x=x
a = p.x
a = p.x - 2
a = 2 * p.x - 2
a = 2 * (p.x + 6) - 2

p.y = a + 5
p.y = p.x + 5

p.translate(1.0, 2.0)

print(p.x, p.y)
print(a)

del p
