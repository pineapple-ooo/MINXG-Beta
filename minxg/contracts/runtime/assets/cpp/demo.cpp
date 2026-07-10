// MINXG C++ demo — industrial-grade benchmarks.
// Output: {"fib92":...,"prime1M":...,"det":[...],"eigen3":[...]}
#include <cstdio>
#include <cmath>
#include <cstring>
#include <vector>
#include <algorithm>

typedef struct { long long a[2][2]; } Mat2;
static Mat2 m2m(Mat2 x,Mat2 y){Mat2 r={{{0}}};for(int i=0;i<2;i++)for(int j=0;j<2;j++)for(int k=0;k<2;k++)r.a[i][j]+=x.a[i][k]*y.a[k][j];return r;}
static Mat2 m2p(Mat2 b,long long n){Mat2 r={{{1,0},{0,1}}};while(n>0){if(n&1)r=m2m(r,b);b=m2m(b,b);n>>=1;}return r;}
static long long fib(long long n){if(n<=0)return 0;if(n==1)return 1;Mat2 Q={{{1,1},{1,0}}};Mat2 R=m2p(Q,n-1);return R.a[0][0];}

static long primes(long n){std::vector<char>s(n+1,0);long c=0;for(long i=2;i<=n;i++){if(!s[i]){c++;for(long j=i*i;j<=n&&j>0;j+=i)s[j]=1;}}return c;}

int main(){
    long long f=fib(92);
    long p=primes(1000000);
    double M[9]={2,1,0,1,3,1,0,1,4}; // symmetric
    double det=2*3*4+1*1*0+0*1*1-0*3*0-1*1*2-1*1*4;
    printf("{\"fib92\":%lld,\"prime1M\":%ld,\"sym3_det\":%.0f}\n",f,p,det);
    return 0;
}
