# coding: utf-8

glt_function = load('pyccel.symbolic.gelato', 'glt_function')
dx           = load('pyccel.symbolic.gelato', 'dx')
dy           = load('pyccel.symbolic.gelato', 'dy')

a  = lambda u,v: dx(u) * dx(v) + dy(u) * dy(v)
ga = glt_function(a)

print(ga)
