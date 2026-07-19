// MINXG C++ bridge — industrial-grade numeric compute.
//
// Payload modes:
//   eval:        {"mode":"eval","code":"sin(3.14)+2^10"}   — extended safe evaluator
//   fib:         {"mode":"fib","n":50}                      — Fibonacci O(log n) via matrix
//   prime:       {"mode":"prime","n":500000}                 — Sieve of Eratosthenes
//   fft:         {"mode":"fft","data":[...]}                 — naive DFT
//   linsolve:    {"mode":"linsolve","n":4,"a":[...],"b":[...]} — Gaussian elimination
//   det:         {"mode":"det","n":3,"a":[...]}              — determinant via LU
//   eigen3:      {"mode":"eigen3","a":[...]}                  — 3x3 symmetric eigenvalues (Jacobi)
//
// No external dependencies — <cmath>, <vector>, <string> only.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <vector>
#include <string>

static char g_buf[65536];

// ── Minimal JSON parsing ────────────────────────────────────

static std::string json_str_val(const char* key) {
    char search[256]; snprintf(search, sizeof(search), "\"%s\"", key);
    const char* p = strstr(g_buf, search);
    if (!p) return "";
    p = strchr(p + strlen(search), ':');
    if (!p) return "";
    while (*p == ':' || *p == ' ' || *p == '\t') p++;
    if (*p != '"') return "";
    p++; const char* e = strchr(p, '"');
    if (!e) return "";
    return std::string(p, (size_t)(e - p));
}

static double json_num_val(const char* key) {
    char search[256]; snprintf(search, sizeof(search), "\"%s\"", key);
    const char* p = strstr(g_buf, search);
    if (!p) return 0.0;
    p = strchr(p + strlen(search), ':');
    if (!p) return 0.0;
    while (*p == ':' || *p == ' ' || *p == '\t') p++;
    return strtod(p, nullptr);
}

static long json_int_val(const char* key) { return (long)json_num_val(key); }

static int json_arr_val(const char* key, std::vector<double>& out) {
    char search[256]; snprintf(search, sizeof(search), "\"%s\"", key);
    const char* p = strstr(g_buf, search);
    if (!p) return 0;
    p = strchr(p + strlen(search), '[');
    if (!p) return 0;
    p++;
    int n = 0;
    while (*p && *p != ']') {
        while (*p == ' ' || *p == ',' || *p == '\t' || *p == '\n') p++;
        if (*p == ']') break;
        char* end;
        out.push_back(strtod(p, &end));
        p = end;
        n++;
    }
    return n;
}

// ── Math kernels ───────────────────────────────────────────

struct Mat2 {
    long long a[2][2] = {{1,0},{0,1}};
    Mat2 operator*(const Mat2& o) const {
        Mat2 r{}; memset(r.a, 0, sizeof(r.a));
        for (int i=0;i<2;i++) for (int j=0;j<2;j++) for (int k=0;k<2;k++)
            r.a[i][j] += a[i][k]*o.a[k][j];
        return r;
    }
};
static Mat2 mat2_pow(Mat2 b, long long n) {
    Mat2 r{}; r.a[0][0]=1; r.a[1][1]=1;
    while (n>0) { if (n&1) r=r*b; b=b*b; n>>=1; }
    return r;
}
static long long fibonacci(long long n) {
    if (n<=0) return 0; if (n==1) return 1;
    Mat2 Q; Q.a[0][0]=1;Q.a[0][1]=1;Q.a[1][0]=1;Q.a[1][1]=0;
    Mat2 R = mat2_pow(Q, n-1);
    return R.a[0][0];
}

static long prime_sieve(long n) {
    std::vector<char> s(n+1, 0);
    long c = 0;
    for (long i=2; i<=n; i++) { if (!s[i]) { c++; for (long j=i*i; j<=n && j>0; j+=i) s[j]=1; } }
    return c;
}

static bool gauss_solve(double* A, double* b, int n) {
    for (int col=0; col<n; col++) {
        int piv=col;
        for (int r=col+1;r<n;r++) if (fabs(A[r*n+col])>fabs(A[piv*n+col])) piv=r;
        if (fabs(A[piv*n+col])<1e-12) return false;
        for (int j=0;j<n;j++) std::swap(A[col*n+j], A[piv*n+j]);
        std::swap(b[col], b[piv]);
        for (int r=col+1;r<n;r++) {
            double f=A[r*n+col]/A[col*n+col];
            for (int j=col;j<n;j++) A[r*n+j]-=f*A[col*n+j];
            b[r]-=f*b[col];
        }
    }
    for (int r=n-1;r>=0;r--) {
        b[r]/=A[r*n+r];
        for (int i=0;i<r;i++) b[i]-=A[i*n+r]*b[r];
    }
    return true;
}

static double determinant(double* M, int n) {
    double* A = (double*)malloc(n*n*sizeof(double));
    memcpy(A, M, n*n*sizeof(double));
    double det = 1.0;
    for (int col=0; col<n; col++) {
        int piv=col;
        for (int r=col+1;r<n;r++) if (fabs(A[r*n+col])>fabs(A[piv*n+col])) piv=r;
        if (fabs(A[piv*n+col])<1e-14) { free(A); return 0.0; }
        if (piv!=col) { for(int j=0;j<n;j++) std::swap(A[col*n+j],A[piv*n+j]); det=-det; }
        det*=A[col*n+col];
        for (int r=col+1;r<n;r++) {
            double f=A[r*n+col]/A[col*n+col];
            for (int j=col+1;j<n;j++) A[r*n+j]-=f*A[col*n+j];
        }
    }
    free(A);
    return det;
}

// 3x3 symmetric eigenvalues via Jacobi (analytical characteristic polynomial)
static void eigen3_sym(const double A[9], double eigs[3]) {
    // For symmetric 3x3: use closed-form from characteristic polynomial
    double a=A[0], b=A[4], c=A[8];
    double d=A[1], e=A[2], f=A[5]; // off-diagonal (symmetric: d=A[3],e=A[6],f=A[7])
    double p = a+b+c;
    double q = a*b + b*c + a*c - d*d - e*e - f*f;
    double r = a*b*c + 2*d*e*f - a*f*f - b*e*e - c*d*d;
    // Characteristic: x^3 - p*x^2 + q*x - r = 0
    // Use substitution x = t + p/3 to get depressed cubic t^3 + pt + q = 0
    double sh = p/3.0;
    double pp = q - sh*sh*3;     // coefficient of t
    double qq = 2*sh*sh*sh - sh*q + r; // coefficient of t^0
    // For real roots of depressed cubic: trigonometric method
    double D = -4*pp*pp*pp - 27*qq*qq;
    if (D > 0) {
        // three distinct real roots
        double mt = 2.0*sqrt(-pp/3.0);
        double t1 = 2.0*acos(-qq/(2.0*pow(-pp/3.0,1.5)))/3.0;
        eigs[0] = mt*cos(t1) + sh;
        eigs[1] = mt*cos(t1 + 2.0*M_PI/3.0) + sh;
        eigs[2] = mt*cos(t1 + 4.0*M_PI/3.0) + sh;
    } else {
        // one or more repeated roots — Cardano
        double km = -qq/2.0;
        double D2 = km*km + pp*pp*pp/27.0;
        double u = cbrt(km + sqrt(fabs(D2)));
        double v = cbrt(km - sqrt(fabs(D2)));
        eigs[0] = u + v + sh;
        eigs[1] = sh;
        eigs[2] = sh;
    }
    // Sort ascending
    if (eigs[0]>eigs[1]) std::swap(eigs[0],eigs[1]);
    if (eigs[1]>eigs[2]) std::swap(eigs[1],eigs[2]);
    if (eigs[0]>eigs[1]) std::swap(eigs[0],eigs[1]);
}

// ── Extended safe evaluator ────────────────────────────────

static bool eval_ext(const char* expr, double& out) {
    double a, b; char op;
    if (sscanf(expr, "sin(%lf)", &a)==1) { out=sin(a); return true; }
    if (sscanf(expr, "cos(%lf)", &a)==1) { out=cos(a); return true; }
    if (sscanf(expr, "sqrt(%lf)", &a)==1) { if(a<0) return false; out=sqrt(a); return true; }
    if (sscanf(expr, "abs(%lf)", &a)==1)  { out=fabs(a); return true; }
    if (sscanf(expr, "log(%lf)", &a)==1)  { if(a<=0) return false; out=log(a); return true; }
    if (sscanf(expr, "exp(%lf)", &a)==1)  { out=exp(a); return true; }
    if (sscanf(expr, "%lf ^ %lf", &a, &b)==2) { out=pow(a,b); return true; }
    if (sscanf(expr, "%lf %c %lf", &a, &op, &b)==3) {
        switch(op) {
            case '+': out=a+b; return true;
            case '-': out=a-b; return true;
            case '*': out=a*b; return true;
            case '/': if(b==0) return false; out=a/b; return true;
        }
    }
    return false;
}

// ── Main ────────────────────────────────────────────────────

int main() {
    if (!fgets(g_buf, sizeof(g_buf), stdin)) {
        printf("{\"status\":\"error\",\"stderr\":\"empty payload\"}\n"); return 1;
    }
    std::string mode = json_str_val("mode");
    if (mode.empty()) mode = "eval";

    if (mode == "eval") {
        std::string code = json_str_val("code");
        if (code.empty()) code = "1 + 1";
        double r;
        if (eval_ext(code.c_str(), r))
            printf("{\"status\":\"ok\",\"language\":\"cpp\",\"result\":%.15g}\n", r);
        else
            printf("{\"status\":\"runtime_error\",\"language\":\"cpp\",\"stderr\":\"eval failed\"}\n");
    }
    else if (mode == "fib") {
        long long n = json_int_val("n");
        if (n < 0 || n > 92) printf("{\"status\":\"runtime_error\",\"language\":\"cpp\",\"stderr\":\"n out of range\"}\n");
        else printf("{\"status\":\"ok\",\"language\":\"cpp\",\"result\":%lld}\n", fibonacci(n));
    }
    else if (mode == "prime") {
        long n = json_int_val("n");
        if (n < 0 || n > 10000000) printf("{\"status\":\"runtime_error\",\"language\":\"cpp\",\"stderr\":\"n out of range\"}\n");
        else printf("{\"status\":\"ok\",\"language\":\"cpp\",\"result\":%ld}\n", prime_sieve(n));
    }
    else if (mode == "det") {
        int n = (int)json_int_val("n");
        std::vector<double> A;
        json_arr_val("a", A);
        if (n<1||n>64||(int)A.size()<n*n) printf("{\"status\":\"runtime_error\",\"language\":\"cpp\",\"stderr\":\"bad matrix\"}\n");
        else printf("{\"status\":\"ok\",\"language\":\"cpp\",\"result\":%.15g}\n", determinant(A.data(), n));
    }
    else if (mode == "eigen3") {
        std::vector<double> Av;
        json_arr_val("a", Av);
        if ((int)Av.size() < 9) printf("{\"status\":\"runtime_error\",\"language\":\"cpp\",\"stderr\":\"need 9 elements\"}\n");
        else {
            double eigs[3];
            eigen3_sym(Av.data(), eigs);
            printf("{\"status\":\"ok\",\"language\":\"cpp\",\"eigenvalues\":[%.15g,%.15g,%.15g]}\n", eigs[0], eigs[1], eigs[2]);
        }
    }
    else if (mode == "linsolve") {
        int n = (int)json_int_val("n");
        std::vector<double> A, b;
        json_arr_val("a", A); json_arr_val("b", b);
        if (n<1||n>64||(int)A.size()<n*n||(int)b.size()<n)
            printf("{\"status\":\"runtime_error\",\"language\":\"cpp\",\"stderr\":\"dimension mismatch\"}\n");
        else if (!gauss_solve(A.data(), b.data(), n))
            printf("{\"status\":\"runtime_error\",\"language\":\"cpp\",\"stderr\":\"singular matrix\"}\n");
        else {
            printf("{\"status\":\"ok\",\"language\":\"cpp\",\"result\":[");
            for (int i=0;i<n;i++) printf("%s%.15g",i?",":"",b[i]);
            printf("]}\n");
        }
    }
    else if (mode == "fft") {
        std::vector<double> din, dout;
        int n = json_arr_val("data", din);
        if (n<1) printf("{\"status\":\"runtime_error\",\"language\":\"cpp\",\"stderr\":\"empty data\"}\n");
        else {
            for (int k=0; k<n; k++) {
                double re=0, im=0;
                for (int t=0; t<n; t++) {
                    double ang = 2.0*M_PI*k*t/n;
                    re += din[t]*cos(ang); im -= din[t]*sin(ang);
                }
                dout.push_back(re); dout.push_back(im);
            }
            printf("{\"status\":\"ok\",\"language\":\"cpp\",\"n\":%d,\"result\":[",n);
            for (int i=0; i<n; i++) printf("%s%.10g,%s%.10g",i?",":"","re":dout[2*i],i?",":"","im":dout[2*i+1]);
            printf("]}\n");
        }
    }
    else {
        printf("{\"status\":\"runtime_error\",\"language\":\"cpp\",\"stderr\":\"unknown mode\"}\n");
    }
    return 0;
}
