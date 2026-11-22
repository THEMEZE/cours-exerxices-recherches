#!/usr/bin/env python3
"""Vérification symbolique/numérique de TOUS les résultats utilisés dans la correction du TD 4.
Usage : python3 verif_physique_td4.py   (nécessite sympy, numpy, scipy)
Chaque bloc imprime OK / ECHEC ; le code de sortie est non nul s'il y a un échec."""
import sympy as sp, numpy as np, sys
from scipy.integrate import solve_ivp
from scipy.special import ellipk, jv
FAILS=[]
def check(name, cond, info=""):
    print(("OK    " if cond else "ECHEC ")+name+(" | "+info if info else ""))
    if not cond: FAILS.append(name)

# ------------------------------------------------------------------ EX1 : équations exactes
a1,a2,d,l,m,g,k=sp.symbols('alpha1 alpha2 d ell m g k',positive=True)
t=sp.symbols('t')
A1=sp.Function('A1')(t); A2=sp.Function('A2')(t)
u=d+l*(sp.sin(A2)-sp.sin(A1)); v=l*(sp.cos(A1)-sp.cos(A2)); L=sp.sqrt(u**2+v**2)
V=-m*g*l*(sp.cos(A1)+sp.cos(A2))+k*(L-d)**2/2
T=m*l**2*(sp.diff(A1,t)**2+sp.diff(A2,t)**2)/2
Lag=T-V
def EL(q): return sp.diff(sp.diff(Lag,sp.diff(q,t)),t)-sp.diff(Lag,q)
eq1=EL(A1); eq2=EL(A2)
# formule "projection sur e_alpha" donnée dans la correction
F=(L-d)*(u*sp.cos(A1)+v*sp.sin(A1))/L
mine1=m*l**2*sp.diff(A1,t,2)+m*g*l*sp.sin(A1)-k*l*F
G=(L-d)*(u*sp.cos(A2)+v*sp.sin(A2))/L
mine2=m*l**2*sp.diff(A2,t,2)+m*g*l*sp.sin(A2)+k*l*G
vals={A1:0.31,A2:-0.52,d:0.7,l:1.1,m:0.2,g:9.81,k:3.0}
def num(e):
    e=e.subs({sp.diff(A1,t,2):0.3,sp.diff(A2,t,2):-0.2,sp.diff(A1,t):0,sp.diff(A2,t):0})
    return float(e.subs(vals).doit())
check("EX1 Lagrange == projection sur e_alpha (P1)", abs(num(eq1-mine1))<1e-9)
check("EX1 Lagrange == projection sur e_alpha (P2)", abs(num(eq2-mine2))<1e-9)
# linéarisation : matrice Hessienne du potentiel en (0,0)
al1,al2=sp.symbols('al1 al2')
Vs=V.subs({A1:al1,A2:al2})
H=sp.hessian(Vs,(al1,al2)).subs({al1:0,al2:0}); H=sp.simplify(H)
check("EX1 Hessienne V(0,0) = [[mgl+kl^2,-kl^2],[-kl^2,mgl+kl^2]]",
      sp.simplify(H-sp.Matrix([[m*g*l+k*l**2,-k*l**2],[-k*l**2,m*g*l+k*l**2]]))==sp.zeros(2,2))
# ordre du premier terme non linéaire dans les équations exactes (développement en eps)
eps=sp.symbols('eps')
expr=sp.simplify((l*F/(l)).subs({A1:eps*sp.Symbol('b1'),A2:eps*sp.Symbol('b2')}))
ser=sp.series(expr,eps,0,4).removeO()
b1,b2=sp.symbols('b1 b2')
# F doit valoir l*(b2-b1)*eps + O(eps^3) (pas de terme en eps^2)
c2=sp.simplify(ser.coeff(eps,2)); c1=sp.simplify(ser.coeff(eps,1))
check("EX1 F = l(b2-b1) eps + 0*eps^2 + O(eps^3)", sp.simplify(c1-l*(b2-b1))==0 and c2==0, f"c2={c2}")
# spring elongation vs x2-x1
def elong(al1_,al2_,dd=0.7,ll=1.1):
    uu=dd+ll*(np.sin(al2_)-np.sin(al1_)); vv=ll*(np.cos(al1_)-np.cos(al2_)); return np.hypot(uu,vv)-dd, ll*(np.sin(al2_)-np.sin(al1_))
for amp in (0.05,0.1,0.2,0.4):
    e,D=elong(0.8*amp,-amp); print(f"      amp={amp}: l-d={e:.5f}  x2-x1={D:.5f}  ecart rel={(e-D)/D:.2e}")
# modes, fréquences (linéaire)
w0s,wcs=sp.symbols('w0s wcs',positive=True)  # w0^2=g/l ; wc^2=k/m
Kmat=sp.Matrix([[w0s+wcs,-wcs],[-wcs,w0s+wcs]])
ev=Kmat.eigenvects()
check("EX1 valeurs propres w0^2, w0^2+2wc^2", sorted([sp.simplify(e[0]) for e in ev],key=str)==sorted([w0s,w0s+2*wcs],key=str))
# battements : identités
x,y=sp.symbols('x y',real=True); tt=sp.symbols('tt',real=True)
w1,w2=sp.symbols('w1 w2',positive=True)
check("EX1 x1=a/2(cos w1t - cos w2t)=a sin((w2-w1)t/2) sin((w1+w2)t/2)",
      sp.simplify(sp.Rational(1,2)*(sp.cos(w1*tt)-sp.cos(w2*tt))-sp.sin((w2-w1)*tt/2)*sp.sin((w1+w2)*tt/2))==0)
check("EX1 x2=a/2(cos w1t + cos w2t)=a cos((w2-w1)t/2) cos((w1+w2)t/2)",
      sp.simplify(sp.Rational(1,2)*(sp.cos(w1*tt)+sp.cos(w2*tt))-sp.cos((w2-w1)*tt/2)*sp.cos((w1+w2)*tt/2))==0)
# faible couplage : w2-w1 ~ wc^2/w0
W0=3.13; WC2=0.5; dw=np.sqrt(W0**2+2*WC2)-W0
check("EX1 faible couplage dw ~ wc^2/w0", abs(dw-WC2/W0)/dw<0.05, f"{dw:.4f} vs {WC2/W0:.4f}")
# conditions pour que S,D découplent : a=d, b=c
a,b,c,dd=sp.symbols('a b c dd')
Amat=sp.Matrix([[a,b],[c,dd]])
cond1=sp.simplify((Amat*sp.Matrix([1,1]))[0]-(Amat*sp.Matrix([1,1]))[1])  # a+b-c-d
cond2=sp.simplify((Amat*sp.Matrix([1,-1]))[0]+(Amat*sp.Matrix([1,-1]))[1]) # a-b+c-d
sol=sp.solve([cond1,cond2],[a,b],dict=True)
check("EX1/2 (1,1),(1,-1) vecteurs propres <=> a=d et b=c", sol and sp.simplify(sol[0][a]-dd)==0 and sp.simplify(sol[0][b]-c)==0, str(sol))

# ------------------------------------------------------------------ DL / petits angles
th=np.array([0.05,0.1,0.2,0.3,0.5,1.0])
print("      theta  err_rel sin≈θ   (θ²/6)   err_rel cos≈1   err_rel cos≈1-θ²/2")
for q in th:
    print(f"      {q:5.2f}  {abs(np.sin(q)-q)/np.sin(q):.2e}   {q*q/6:.2e}   {abs(np.cos(q)-1)/np.cos(q):.2e}   {abs(np.cos(q)-(1-q*q/2))/np.cos(q):.2e}")
def Tratio(th0): return 2/np.pi*ellipk(np.sin(th0/2)**2)
for deg in (5,10,20,30,60,90,120):
    r=Tratio(np.radians(deg)); approx=1+np.radians(deg)**2/16
    print(f"      theta0={deg:3d}°  T/T0={r:.5f}  (1+θ0²/16={approx:.5f})")
check("DL T(10°)/T0 = 1.0019", abs(Tratio(np.radians(10))-1.0019)<2e-4)
check("DL T(30°)/T0 = 1.0174", abs(Tratio(np.radians(30))-1.0174)<2e-4)
check("DL T(90°)/T0 = 1.1803", abs(Tratio(np.radians(90))-1.1803)<2e-4)
s=sp.symbols('s')
check("DL sin = s - s^3/6 + s^5/120", sp.series(sp.sin(s),s,0,7).removeO()==s-s**3/6+s**5/120)
check("DL cos = 1 - s^2/2 + s^4/24", sp.series(sp.cos(s),s,0,6).removeO()==1-s**2/2+s**4/24)

# ------------------------------------------------------------------ EX2
w0=sp.symbols('w0',positive=True)
x1,x2=sp.symbols('x1 x2')
Kk=sp.Matrix([[3,-2],[-2,6]])
check("EX2 valeurs propres 2 et 7", sorted(Kk.eigenvals().keys())==[2,7])
S,D=sp.symbols('S D')
# ẍ = -w0^2 Kk x  ->  S'' , D''
xdd=-w0**2*Kk*sp.Matrix([x1,x2]); Sdd=sp.expand((xdd[0]+xdd[1]).subs({x1:(S+D)/2,x2:(S-D)/2})); Ddd=sp.expand((xdd[0]-xdd[1]).subs({x1:(S+D)/2,x2:(S-D)/2}))
check("EX2 S''= -w0²(5/2 S - 3/2 D)", sp.simplify(Sdd+w0**2*(sp.Rational(5,2)*S-sp.Rational(3,2)*D))==0)
check("EX2 D''= -w0²(-3/2 S + 13/2 D)", sp.simplify(Ddd+w0**2*(-sp.Rational(3,2)*S+sp.Rational(13,2)*D))==0)
official_S=-w0**2*(S/2 - 3*D/2); official_D=-w0**2*(13*S/2 - 3*D/2)
check("EX2 équations (S,D) du corrigé officiel sont FAUSSES", sp.simplify(Sdd-official_S)!=0 and sp.simplify(Ddd-official_D)!=0)
beta=sp.symbols('beta')
check("EX2 combinaisons x1+beta x2 : beta=1/2 et -2", sorted(sp.solve(2*beta**2+3*beta-2,beta))==[-2,sp.Rational(1,2)])
# 4e ordre
X1=sp.Function('X1')(t)
X2e=(sp.diff(X1,t,2)+3*w0**2*X1)/(2*w0**2)
eq4=sp.diff(X2e,t,2)+6*w0**2*X2e-2*w0**2*X1
r=sp.symbols('r'); ch=sp.expand(sp.simplify(eq4.subs(X1,sp.exp(r*t)).doit()/sp.exp(r*t))*2*w0**2)
check("EX2 4e ordre : r^4+9w0²r²+14w0⁴ = 0", sp.simplify(ch-(r**4+9*w0**2*r**2+14*w0**4))==0, str(sp.factor(ch)))
# angle de mélange
check("EX2 tan(2θ)=4/3, tanθ=1/2", abs(np.tan(0.5*np.arctan2(4,3))-0.5)<1e-12)

# ------------------------------------------------------------------ EX3
W1,W2,Om,w=sp.symbols('W1 W2 Om w',positive=True)
Delta=(W1**2+Om**2-w**2)*(W2**2+Om**2-w**2)-Om**4
poly=sp.expand(Delta-(w**4-(W1**2+W2**2+2*Om**2)*w**2+W1**2*W2**2+Om**2*(W1**2+W2**2)))
check("EX3 quartique biquadratique", poly==0)
disc=sp.expand((W1**2+W2**2+2*Om**2)**2-4*(W1**2*W2**2+Om**2*(W1**2+W2**2))-((W1**2-W2**2)**2+4*Om**4))
check("EX3 discriminant = (W1²-W2²)²+4Om⁴", disc==0)
# forcé : Cramer
a0=sp.symbols('a0')
Msys=sp.Matrix([[W1**2+Om**2-w**2,-Om**2],[-Om**2,W2**2+Om**2-w**2]]); rhs=sp.Matrix([W1**2*a0,0])
solc=sp.simplify(Msys.LUsolve(rhs))
check("EX3 A1 = a0 W1²(W2²+Om²-w²)/Δ", sp.simplify(solc[0]-a0*W1**2*(W2**2+Om**2-w**2)/Delta)==0)
check("EX3 A2 = a0 W1² Om²/Δ", sp.simplify(solc[1]-a0*W1**2*Om**2/Delta)==0)
gg,ll_,mm,kc=9.81,0.66,0.1,1.0
wc=np.sqrt(gg/ll_+kc/mm); print(f"      EX3 w={wc:.4f} rad/s  T={2*np.pi/wc:.4f} s")
check("EX3 T = 1.26 s", abs(2*np.pi/wc-1.26)<0.005)
# rapport des amplitudes : signe, en phase / opposition
for (w1v,w2v,omv) in [(3.,5.,2.),(4.,4.,1.5),(6.,2.,3.)]:
    Mx=np.array([[w1v**2+omv**2,-omv**2],[-omv**2,w2v**2+omv**2]]); ev,evec=np.linalg.eigh(Mx)
    r1=evec[1,0]/evec[0,0]; r2=evec[1,1]/evec[0,1]
    ok=(r1>0) and (r2<0) and np.isclose(r1,(w1v**2+omv**2-ev[0])/omv**2) and np.isclose(r2,(w1v**2+omv**2-ev[1])/omv**2)
    gap=ev[1]-ev[0]
    check(f"EX3 mode bas en phase, mode haut en opposition, ratio=(W1²+Om²-w²)/Om² (W1={w1v},W2={w2v},Om={omv})", ok and gap>=2*omv**2-1e-12, f"r'={r1:.3f} r''={r2:.3f} gap={gap:.3f}>=2Om²={2*omv**2}")
# A2 à l'antirésonance
sol_anti=sp.simplify(solc[1].subs(w**2,W2**2+Om**2))
check("EX3 antirésonance : A2 = -a0 W1²/Om² = -a0 k/kc", sp.simplify(sol_anti+a0*W1**2/Om**2)==0)

# ------------------------------------------------------------------ EX4
NA=6e23; mC=12e-3/NA; mO=16e-3/NA; mu=mC*mO/(mC+mO); f0=3e8/4.6e-6
kCO=4*np.pi**2*f0**2*mu
print(f"      EX4 mC={mC:.3e} mO={mO:.3e} mu={mu:.4e} f0={f0:.4e} Hz  k={kCO:.1f} N/m  nu~={1/4.6e-4:.0f} cm-1  hf0={6.626e-34*f0/1.602e-19:.3f} eV")
check("EX4 k ≈ 1919 N/m", abs(kCO-1919)<3)
check("EX4 k(T=1s, m=0.1kg)=2π²m/T²≈1.97", abs(2*np.pi**2*0.1-1.974)<0.002)
m1s,m2s,ks=sp.symbols('m1 m2 k',positive=True)
Mm=sp.diag(m1s,m2s); Kc=ks*sp.Matrix([[1,-1],[-1,1]])
det=sp.factor(sp.expand((Kc-w**2*Mm).det()))
check("EX4 det(K-w²M)=w²(m1m2w²-k(m1+m2))", sp.simplify(det-w**2*(m1s*m2s*w**2-ks*(m1s+m2s)))==0, str(det))
u0=sp.Matrix([1,1]); u1=sp.Matrix([m2s,-m1s])
check("EX4 u0,u1 M-orthogonaux (pas euclidiens)", sp.simplify((u0.T*Mm*u1)[0])==0 and sp.simplify((u0.T*u1)[0])!=0)
# Lennard-Jones k = 57.15 eps/sigma^2
r_,e_,s_=sp.symbols('r e s',positive=True); VLJ=4*e_*((s_/r_)**12-(s_/r_)**6); r0=2**sp.Rational(1,6)*s_
kLJ=sp.simplify(sp.diff(VLJ,r_,2).subs(r_,r0)); print("      EX4 k_LJ =",kLJ, float(kLJ.subs({e_:1,s_:1})))
check("EX4 k_LJ=57.15 eps/sigma²", abs(float(kLJ.subs({e_:1,s_:1}))-57.1464)<1e-2)

# ------------------------------------------------------------------ EX5 (ressort à hauteur h)
l_,h_,m_,k_,g_=1.0,0.5,0.2,0.4,9.81
w0_=np.sqrt(g_/l_); wc2=k_*h_**2/(m_*l_**2); w2_=np.sqrt(w0_**2+2*wc2); Tb=2*np.pi/(w2_-w0_); kappa=wc2/(w0_**2+wc2)
print(f"      EX5 w0={w0_:.4f} wc²={wc2:.4f} w2={w2_:.4f} Tb={Tb:.2f} s  Tb~={2*np.pi*w0_/wc2:.2f} kappa={kappa:.5f}")
# énergies : E_c,max/E = wc²/(w0²+wc²)
def Fspring(a1,a2,hh,d):
    u=d+hh*(np.sin(a2)-np.sin(a1)); v=hh*(np.cos(a1)-np.cos(a2)); L=np.hypot(u,v)
    return (L-d)*(u*np.cos(a1)+v*np.sin(a1))/L
dd=[]
for e in (2e-2,1e-2):
    a1,a2=0.7*e,-0.4*e; dd.append(abs(Fspring(a1,a2,h_,1.0)-h_*(np.sin(a2)-np.sin(a1))*np.cos(a1)))
check("EX5 force du ressort = h(sinα2-sinα1)cosα1 + O(ε⁴) (ratio d'erreurs ≈ 16)", 12<dd[0]/dd[1]<20, f"err={dd} ratio={dd[0]/dd[1]:.1f}")
def rhs5(tt,y,w0,wc2):
    a1,a2,v1,v2=y; return [v1,v2,-w0**2*a1+wc2*(a2-a1),-w0**2*a2-wc2*(a2-a1)]
sol5=solve_ivp(rhs5,[0,3*Tb],[0.1,0,0,0],args=(w0_,wc2),rtol=1e-10,atol=1e-12,dense_output=True)
tg=np.linspace(0,3*Tb,6000); Y=sol5.sol(tg); 
E=0.5*m_*l_**2*(Y[2]**2+Y[3]**2)+0.5*m_*g_*l_*(Y[0]**2+Y[1]**2)+0.5*k_*h_**2*(Y[0]-Y[1])**2
Ec=0.5*k_*h_**2*(Y[0]-Y[1])**2
check("EX5 énergie totale conservée", (E.max()-E.min())/E.mean()<1e-7)
check("EX5 max(Ec)/E ≈ κ", abs(Ec.max()/E.mean()-kappa)/kappa<0.02, f"{Ec.max()/E.mean():.5f} vs {kappa:.5f}")
E1=0.5*m_*l_**2*Y[2]**2+0.5*m_*g_*l_*Y[0]**2
check("EX5 transfert quasi total (E1 min / E < 2κ)", E1.min()/E.mean()<2*kappa, f"min E1/E={E1.min()/E.mean():.4f}")
i1=np.argmin(np.where(tg<=Tb,E1,np.inf))
check("EX5 premier minimum de E1 à Tb/2 (transfert complet en Tb/2)", abs(tg[i1]-Tb/2)/Tb<0.02, f"t_min={tg[i1]:.2f} Tb/2={Tb/2:.2f}")

# ------------------------------------------------------------------ EX6 (3 masses)
K3=np.array([[2,-1,0],[-1,2,-1],[0,-1,2]],float); ev3,evec3=np.linalg.eigh(K3)
check("EX6 valeurs propres 2-√2, 2, 2+√2", np.allclose(ev3,[2-np.sqrt(2),2,2+np.sqrt(2)]))
check("EX6 vecteurs propres (1,√2,1),(1,0,-1),(1,-√2,1)", np.allclose(np.abs(evec3[:,0]),np.array([1,np.sqrt(2),1])/2) and np.allclose(np.abs(evec3[:,1]),np.array([1,0,1])/np.sqrt(2)) )
check("EX6 ω_p²=4 sin²(pπ/8)", np.allclose(ev3,[4*np.sin(p*np.pi/8)**2 for p in (1,2,3)]))
epsl=0.02; Kp=K3.copy(); Mp=np.diag([1,1,1+epsl]); from scipy.linalg import eigh
evp,_=eigh(K3,Mp)
pred=ev3-epsl*ev3*evec3[2,:]**2
check("EX6 Rayleigh : δ(ω_p²)=-ε ω_p² u_p3²", np.allclose(evp,pred,atol=2*epsl**2*4), f"num={evp} pred={pred}")
# parité : sous-bloc symétrique
Bs=np.array([[2,-2],[-1,2]],float); check("EX6 bloc symétrique valeurs propres 2±√2", np.allclose(sorted(np.linalg.eigvals(Bs).real),[2-np.sqrt(2),2+np.sqrt(2)]))

# ------------------------------------------------------------------ EX7 (désaccord)
def ex7(Wa2,Wb2,O2,A0=1.0,tmax=None):
    Km=np.array([[Wa2+O2,-O2],[-O2,Wb2+O2]]); ev,evec=np.linalg.eigh(Km); return Km,ev,evec
W0sq=100.; O2=0.5
for Dl in (0.0,0.5,1.0,2.0,4.0):
    Km,ev,evec=ex7(W0sq-Dl/2,W0sq+Dl/2,O2)
    gap=ev[1]-ev[0]; gap_th=2*np.sqrt((Dl/2)**2+O2**2)
    th_=0.5*np.arctan2(2*O2,Dl); frac_th=np.sin(2*th_)**2
    # simulation : x1(0)=1
    tt_=np.linspace(0,4*2*np.pi/(np.sqrt(ev[1])-np.sqrt(ev[0])),40001)
    om=np.sqrt(ev); c0=evec.T@np.array([1.,0.])
    X=(evec*c0)@np.cos(np.outer(om,tt_)); V=-(evec*c0*om[:,None].T)@np.sin(np.outer(om,tt_))
    Wk=lambda x,vx,W2:0.5*vx**2+0.5*W2*x**2
    E2=Wk(X[1],V[1],W0sq+Dl/2); Etot=Wk(1.0,0,W0sq-Dl/2)
    frac_num=E2.max()/Etot
    check(f"EX7 gap & fraction transférée (Δ={Dl}) : gap={gap:.4f}/{gap_th:.4f}, fraction num={frac_num:.4f} th sin²2θ={frac_th:.4f}",
          abs(gap-gap_th)<1e-9 and abs(frac_num-frac_th)<0.02)
# période de battement généralisée
Dl=2.0; Km,ev,evec=ex7(W0sq-Dl/2,W0sq+Dl/2,O2); Tb7=2*np.pi/(np.sqrt(ev[1])-np.sqrt(ev[0])); w0m=np.sqrt(W0sq)
dwr=(Dl/(2*w0m)); Tb_th=2*np.pi/np.sqrt(dwr**2+(O2/w0m)**2)
check("EX7 Tb ≈ 2π/√(δ²+(Ω²/ω0)²)", abs(Tb7-Tb_th)/Tb7<0.01, f"{Tb7:.3f} vs {Tb_th:.3f}")

# ------------------------------------------------------------------ EX8 (non linéaire)
def exact_rhs(tt,y,w0sq,kom,dlen,ell):
    al1,al2,v1,v2=y
    u_=dlen+ell*(np.sin(al2)-np.sin(al1)); v__=ell*(np.cos(al1)-np.cos(al2)); L_=np.hypot(u_,v__)
    fac=(L_-dlen)/L_
    F1=fac*(u_*np.cos(al1)+v__*np.sin(al1)); F2=fac*(u_*np.cos(al2)+v__*np.sin(al2))
    return [v1,v2,-w0sq*np.sin(al1)+kom*F1/ell,-w0sq*np.sin(al2)-kom*F2/ell]
ell=1.0; gv=9.81; w0sq=gv/ell; dlen=1.0
def period(y0,args,tmax=40):
    sol=solve_ivp(exact_rhs,[0,tmax],y0,args=args,rtol=1e-11,atol=1e-13,dense_output=True,max_step=0.01)
    tt_=np.linspace(0,tmax,400001); a=sol.sol(tt_)[0]
    idx=np.where((a[:-1]>0)&(a[1:]<=0))[0]; tz=tt_[idx]-a[idx]*(tt_[idx+1]-tt_[idx])/(a[idx+1]-a[idx])
    return np.mean(np.diff(tz))*1.0, sol
# sym : période d'un pendule
for A in (0.2,0.6,1.0):
    Ts,_=period([A,A,0,0],(w0sq,2.0,dlen,ell)); T0=2*np.pi/np.sqrt(w0sq)*Tratio(A)
    check(f"EX8 mode symétrique exact = pendule non linéaire (A={A})", abs(Ts-T0)/T0<2e-4, f"{Ts:.5f} vs {T0:.5f}")
# antisym : réduction 1D
kom=2.0
for A in (0.1,0.3):
    Ta,_=period([A,-A,0,0],(w0sq,kom,dlen,ell))
    f=lambda tt,y:[y[1],-w0sq*np.sin(y[0])-kom*np.sin(2*y[0])]
    sol=solve_ivp(f,[0,40],[A,0],rtol=1e-11,atol=1e-13,dense_output=True,max_step=0.01); tt_=np.linspace(0,40,400001); a=sol.sol(tt_)[0]
    idx=np.where((a[:-1]>0)&(a[1:]<=0))[0]; tz=tt_[idx]-a[idx]*(tt_[idx+1]-tt_[idx])/(a[idx+1]-a[idx]); T1d=np.mean(np.diff(tz))
    wa=np.sqrt(w0sq+2*kom); Tpl=2*np.pi/(wa-A**2*(w0sq+8*kom)/(16*wa))
    check(f"EX8 mode antisym = 1D β''=-w0² sinβ-(k/m)sin2β ; Poincaré-Lindstedt (A={A})", abs(Ta-T1d)/T1d<1e-5 and abs(Tpl-T1d)/T1d<3e-3, f"T2D={Ta:.5f} T1D={T1d:.5f} PL={Tpl:.5f}")
# Floquet : stabilité du mode symétrique
def floquet_max(A,kom):
    wsy=np.sqrt(w0sq)*1.0
    # période exacte du pendule
    Tp=2*np.pi/np.sqrt(w0sq)*Tratio(A)
    def rhs(tt,Y):
        al,v=Y[0],Y[1]; q=Y[2:4]; p=Y[4:6]
        return [v,-w0sq*np.sin(al), q[1]*0+0,0,0,0]
    # monodromie du système linéarisé pour q: q''=-(w0² cos α + 2 kom cos²α) q
    def full(tt,Y):
        al,v,Q=Y[0],Y[1],Y[2:].reshape(2,2)  # colonnes : 2 solutions (q,q')
        c=np.cos(al); coef=w0sq*c+2*kom*c*c
        dQ=np.vstack([Q[1],-coef*Q[0]])
        return np.concatenate([[v,-w0sq*np.sin(al)],dQ.ravel()])
    Y0=np.concatenate([[A,0],np.eye(2).ravel()])
    sol=solve_ivp(full,[0,Tp],Y0,rtol=1e-12,atol=1e-14); Mon=sol.y[2:,-1].reshape(2,2)
    return np.max(np.abs(np.linalg.eigvals(Mon)))
kom=0.02*w0sq   # ω_c²/ω0² = 0.02
wc_=np.sqrt(kom); Ac=np.sqrt(8*kom/(w0sq+6*kom)); print(f"      EX8 ω_c/ω0={wc_/np.sqrt(w0sq):.4f}  A_c(th)={Ac:.4f}  (2√2 ωc/ω0={2*np.sqrt(2)*wc_/np.sqrt(w0sq):.4f})")
mu_below=floquet_max(0.8*Ac,kom); mu_above=floquet_max(1.3*Ac,kom)
check("EX8 stable sous le seuil, instable au-dessus (Floquet exact)", mu_below<=1+1e-6 and mu_above>1+1e-4, f"|μ|max(0.8Ac)={mu_below:.6f} ; |μ|max(1.3Ac)={mu_above:.6f}")
# seuil numérique
from scipy.optimize import brentq
Anum=brentq(lambda A:floquet_max(A,kom)-1-1e-9,0.8*Ac,1.4*Ac,xtol=1e-6)
check("EX8 seuil numérique ≈ A_c théorique (<5%)", abs(Anum-Ac)/Ac<0.05, f"A_c num={Anum:.4f} th={Ac:.4f}")

# ------------------------------------------------------------------ EX9 (anneau)
for N in (2,3,4,5,6,8):
    Kr=np.zeros((N,N))
    for n in range(N):
        Kr[n,n]+=2; Kr[n,(n+1)%N]-=1; Kr[n,(n-1)%N]-=1
    if N==2: Kr=np.array([[2,-2],[-2,2]],float)
    ev_=np.sort(np.linalg.eigvalsh(Kr)); th_=np.sort([4*np.sin(np.pi*p/N)**2 for p in range(N)])
    check(f"EX9 anneau N={N} : ω_p²=4ω0² sin²(πp/N)", np.allclose(ev_,th_))
# Bessel
tgrid=np.linspace(0,6,7); N=400; ps=np.arange(N)
def xn(n,t_):  # chaîne en anneau grand N
    return (1/N)*np.sum(np.cos(2*np.sqrt(1)*np.sin(np.pi*ps/N)*2*t_*0+2*np.sin(np.pi*ps/N)*t_)*np.cos(2*np.pi*ps*n/N))
errs=[abs(xn(n,t_)-jv(2*n,2*t_)) for n in (0,1,2,3) for t_ in (0.5,2.0,5.0)]
check("EX9 x_n(t)=a J_{2n}(2ω0 t) (grand anneau, avant retour du signal)", max(errs)<1e-6, f"max err={max(errs):.2e}")


# ------------------------------------------------------------------ Contrôles des valeurs numériques citées dans les YAML
w0c=np.sqrt(20/0.1); wp=[w0c*np.sqrt(2-np.sqrt(2)),w0c*np.sqrt(2),w0c*np.sqrt(2+np.sqrt(2))]
check("EX6 ω1,ω2,ω3 = 10.82, 20.0, 26.13 rad/s ; f = 1.72, 3.18, 4.16 Hz", np.allclose(wp,[10.82,20.0,26.13],atol=0.01) and np.allclose([x/2/np.pi for x in wp],[1.72,3.18,4.16],atol=0.01), str(wp))
a_=1.0; tt=np.linspace(0,3,7)
Xn=np.array([[a_/4*np.cos(wp[0]*t)+a_/2*np.cos(wp[1]*t)+a_/4*np.cos(wp[2]*t),
              np.sqrt(2)*a_/4*(np.cos(wp[0]*t)-np.cos(wp[2]*t)),
              a_/4*np.cos(wp[0]*t)-a_/2*np.cos(wp[1]*t)+a_/4*np.cos(wp[2]*t)] for t in tt])
Kx=20*K3; Mx=0.1*np.eye(3)
solx=solve_ivp(lambda t,y:np.concatenate([y[3:],-np.linalg.solve(Mx,Kx@y[:3])]),[0,3],[a_,0,0,0,0,0],t_eval=tt,rtol=1e-11,atol=1e-13)
check("EX6 solution modale x1,x2,x3 = intégration numérique", np.allclose(solx.y[:3].T,Xn,atol=1e-7))
# EX7 périodes de battement
def Tb7f(D,O2=0.5,W0=100.):
    ev=np.linalg.eigvalsh(np.array([[W0-D/2+O2,-O2],[-O2,W0+D/2+O2]])); return 2*np.pi/(np.sqrt(ev[1])-np.sqrt(ev[0]))
check("EX7 T_b(Δ=0)=125.9 s et T_b(Δ=2)=56 s", abs(Tb7f(0)-125.9)<0.3 and abs(Tb7f(2)-56.2)<0.5, f"{Tb7f(0):.2f} {Tb7f(2):.2f}")
check("EX7 fraction transférée 20 % à Δ=2 ; 50 % à Δ=2Ω²", abs(4*0.25/(4+1)-0.2)<1e-12 and abs(4*0.25/(1+1)-0.5)<1e-12)
# EX8 valeurs numériques
check("EX8 T(A=0.6)=2.052 s, T(1.0)=2.139 s", abs(2*np.pi/np.sqrt(9.81)*Tratio(0.6)-2.0522)<2e-3 and abs(2*np.pi/np.sqrt(9.81)*Tratio(1.0)-2.1391)<2e-3)
check("EX8 A_c(κ=0.02ω0²)=0.378", abs(np.sqrt(8*0.02/(1+6*0.02))-0.378)<1e-3)
# EX9 N=4 solution
w=np.sqrt(2.); tt=np.linspace(0,5,6)
K4=2*np.eye(4)-np.roll(np.eye(4),1,0)-np.roll(np.eye(4),-1,0)
s4=solve_ivp(lambda t,y:np.concatenate([y[4:],-K4@y[:4]]),[0,5],[1,0,0,0,0,0,0,0],t_eval=tt,rtol=1e-11,atol=1e-13)
x0=0.25*(1+np.cos(2*tt))+0.5*np.cos(w*tt); x1=0.25*(1-np.cos(2*tt)); x2=0.25*(1+np.cos(2*tt))-0.5*np.cos(w*tt)
check("EX9 N=4 : x0,x1=x3,x2 analytiques = numérique", np.allclose(s4.y[0],x0,atol=1e-7) and np.allclose(s4.y[1],x1,atol=1e-7) and np.allclose(s4.y[3],x1,atol=1e-7) and np.allclose(s4.y[2],x2,atol=1e-7))
check("EX9 N=6 fréquences 0, ω0 (x2), √3ω0 (x2), 2ω0", np.allclose(sorted(np.sqrt(np.abs(np.linalg.eigvalsh(2*np.eye(6)-np.roll(np.eye(6),1,0)-np.roll(np.eye(6),-1,0))))),[0,1,1,np.sqrt(3),np.sqrt(3),2],atol=1e-6))
# EX5 numériques
check("EX5 ω0=3.132, ω2=3.288, Tb=40.3 s, κ=4.9 %", abs(w0_-3.132)<1e-3 and abs(w2_-3.288)<1e-3 and abs(Tb-40.3)<0.1 and abs(kappa-0.0485)<5e-4)

print()
print("ECHECS :",FAILS if FAILS else "aucun")
sys.exit(1 if FAILS else 0)
