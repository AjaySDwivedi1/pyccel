n=100
#Pi_estime=acos(-1.0) # TODO not available yet

#$ header f(double)
def f(x):
    return 1.0/(1.0 + x*x)

#TODO fix h is processed as int
h = 1.0/n
for k in range(1,1000):
    Pi_calcule = 0.0
    for i in range(1, n):
        x = h * i
        Pi_calcule = Pi_calcule + f(x)
    Pi_calcule = h * Pi_calcule
print(Pi_calcule)
#ecart = Pi_estime - Pi_calcule
#print(ecart)

