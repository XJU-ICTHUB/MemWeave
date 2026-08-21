// Generic reference implementation for the GPU memory-constrained scheduling problem.
// It combines an event-driven constructor, exact feasibility checks, a fixed family of
// priority functions, and time-bounded local improvement. Build with GCC 17 or newer.

#include <bits/stdc++.h>
#include <unistd.h>
using namespace std;

static constexpr int HB = 4096;
static constexpr int HMASK = HB - 1;
static_assert((HB & (HB - 1)) == 0, "HB must be a power of two");

struct Decision { int S, id, k; };

struct Policy {
    long long quadraticWeight = 1000;
    int earlyStop = 0;
};

// Online constructor used while requests are still arriving.
struct Sched {
    int N, K, B;
    vector<int> Mcap;
    vector<int> Lin, Lout, Arr;
    vector<char> launched;
    vector<int> bmem, bcnt, bstamp;
    vector<multiset<long long>> activeEnds;
    vector<int> pending;
    unordered_map<long long, vector<int>> endGpusAt;
    long long launchedCount = 0;
    Policy pol;

    long long opCount = 0;
    long long opBudget = 1500000000LL;
    bool degraded = false;
    int degCap = 256;

    void init(int n, int k, int b, const vector<int>& M) {
        N = n; K = k; B = b;
        Mcap.assign(K + 1, 0);
        for (int i = 1; i <= K; i++) Mcap[i] = M[i];
        Lin.assign(N + 1, 0); Lout.assign(N + 1, 0); Arr.assign(N + 1, 0);
        launched.assign(N + 1, 0);
        bmem.assign((long long)(K + 1) * HB, 0);
        bcnt.assign((long long)(K + 1) * HB, 0);
        bstamp.assign((long long)(K + 1) * HB, -1);
        activeEnds.assign(K + 1, multiset<long long>());
        pending.clear(); endGpusAt.clear(); launchedCount = 0;
        opCount = 0; degraded = false;
        endGpusAt.reserve(1 << 12);
    }

    inline int memAt(int k, long long tau) {
        int idx = k * HB + (int)(tau & HMASK);
        return bstamp[idx] == (int)tau ? bmem[idx] : 0;
    }
    inline int cntAt(int k, long long tau) {
        int idx = k * HB + (int)(tau & HMASK);
        return bstamp[idx] == (int)tau ? bcnt[idx] : 0;
    }
    inline void touch(int k, long long tau, int dm, int dc) {
        int idx = k * HB + (int)(tau & HMASK);
        if (bstamp[idx] != (int)tau) { bstamp[idx] = (int)tau; bmem[idx] = 0; bcnt[idx] = 0; }
        bmem[idx] += dm; bcnt[idx] += dc;
    }

    inline bool feasible(int i, int k, long long s, int& peakOut) {
        int li = Lin[i], lo = Lout[i];
        long long e = s + lo - 1;
        int cap = Mcap[k];
        if ((long long)li + lo > cap) return false;
        if (cntAt(k, s) + 1 > B) return false;
        int peak = 0;
        long long ops = 1;
        {
            int m = memAt(k, e);
            if (m + li + lo > cap) { opCount += 1; return false; }
            if (m > peak) peak = m;
        }
        auto& S = activeEnds[k];
        for (auto it = S.lower_bound(s); it != S.end() && *it < e; ++it) {
            long long C = *it;
            int m = memAt(k, C);
            int add = li + (int)(C - s + 1);
            ++ops;
            if (m + add > cap) { opCount += ops; return false; }
            if (m > peak) peak = m;
        }
        opCount += ops;
        peakOut = peak;
        return true;
    }

    void place(int i, int k, long long s) {
        int li = Lin[i], lo = Lout[i];
        long long e = s + lo - 1;
        for (long long tau = s; tau <= e; ++tau) touch(k, tau, li + (int)(tau - s + 1), 1);
        launched[i] = 1; launchedCount++; endGpusAt[e].push_back(k);
        activeEnds[k].insert(e);
    }

    int chooseGpu(int i, long long s, const vector<int>* active) {
        int best = -1;
        long long bestScore = LLONG_MAX;
        int na = active ? (int)active->size() : K;
        for (int idx2 = 0; idx2 < na; idx2++) {
            int k = active ? (*active)[idx2] : idx2 + 1;
            int peak;
            if (!feasible(i, k, s, peak)) continue;
            long long score = peak;
            if (score < bestScore) { bestScore = score; best = k; }
        }
        return best < 0 ? 0 : best;
    }

    void sortPending() {
        auto &L = Lin, &O = Lout;
        auto cmp = [&](int a, int b) -> bool {
            long long ka = (long long)L[a] * O[a] * 1000
                         + pol.quadraticWeight * (long long)O[a] * O[a];
            long long kb = (long long)L[b] * O[b] * 1000
                         + pol.quadraticWeight * (long long)O[b] * O[b];
            if (ka != kb) return ka < kb;
            int sa = L[a] + O[a], sb = L[b] + O[b];
            if (sa != sb) return sa < sb;
            return a < b;
        };
        sort(pending.begin(), pending.end(), cmp);
    }

    vector<Decision> step(long long t, const vector<int>& arrIds) {
        vector<Decision> dec;
        for (int id : arrIds) pending.push_back(id);

        vector<int> dirty;
        auto it = endGpusAt.find(t);
        if (it != endGpusAt.end()) {
            dirty = std::move(it->second);
            endGpusAt.erase(it);
            sort(dirty.begin(), dirty.end());
            dirty.erase(unique(dirty.begin(), dirty.end()), dirty.end());
        }
        bool hasArrivals = !arrIds.empty();
        if ((!hasArrivals && dirty.empty()) || pending.empty()) return dec;

        if (!degraded && opCount > opBudget) degraded = true;
        const vector<int>* active = nullptr;
        if (degraded && !hasArrivals) active = &dirty;

        long long s = t + 1;
        sortPending();
        vector<int> still;
        still.reserve(pending.size());
        int examined = 0;
        int consecFail = 0;
        bool stopScan = false;
        for (int i : pending) {
            if (stopScan || (degraded && examined >= degCap)) { still.push_back(i); continue; }
            ++examined;
            int k = chooseGpu(i, s, active);
            if (k > 0) { place(i, k, s); dec.push_back({(int)s, i, k}); consecFail = 0; }
            else {
                still.push_back(i);
                if (pol.earlyStop > 0 && ++consecFail >= pol.earlyStop) stopScan = true;
            }
        }
        pending.swap(still);
        return dec;
    }
};

// Offline optimizer used when a complete pending set is known.
namespace solv {
using namespace std;

static constexpr double SWEEP_FRACTION = 0.5;
static constexpr long long SFX_SLACK_DIVISOR = 6400;
static constexpr double SFX_BACK_BIAS = -1.5;
static constexpr int CHECKPOINT_DIVISOR = 16;
static constexpr long long STALL_THRESHOLD = 300;
static constexpr int BOOTSTRAP_PASSES = 24;
static constexpr double BOOTSTRAP_ALPHA = 0.025;
static constexpr int MASK_BLOCK_SIZE = 128;

struct Test {
    int N, K, B;
    vector<int> M, Lin, Lout, Arr;
};

typedef void (*MaskFn)(unsigned char*, const int*, const int*, const int*,
                       size_t, size_t, int, int, int);
__attribute__((optimize("O3","tree-vectorize")))
static void maskKernelPlain(unsigned char* cd, const int* Li, const int* Lo, const int* Sm,
                            size_t b0, size_t b1, int cap, int thr, int cm){
    for(size_t j=b0;j<b1;j++)
        cd[j] |= (unsigned char)(((int)(Sm[j]<=cap)) & (((int)(Li[j]<=thr)) | ((int)(Lo[j]<=cm))));
}
#if defined(__x86_64__) || defined(__i386__)
__attribute__((optimize("O3","tree-vectorize"),target("avx2")))
static void maskKernelAVX2(unsigned char* cd, const int* Li, const int* Lo, const int* Sm,
                           size_t b0, size_t b1, int cap, int thr, int cm){
    for(size_t j=b0;j<b1;j++)
        cd[j] |= (unsigned char)(((int)(Sm[j]<=cap)) & (((int)(Li[j]<=thr)) | ((int)(Lo[j]<=cm))));
}
#endif
static MaskFn pickMaskFn(){
#if defined(__x86_64__) || defined(__i386__)
    if(__builtin_cpu_supports("avx2")) return maskKernelAVX2;
#endif
    return maskKernelPlain;
}
static MaskFn g_maskKernel = pickMaskFn();

typedef void (*MaskFn16)(unsigned char*, const short*, const short*,
                         size_t, size_t, short, short, short);
__attribute__((optimize("O3","tree-vectorize")))
static void mask16AssignPlain(unsigned char* cd, const short* Li, const short* Lo,
                              size_t b0, size_t b1, short cap, short thr, short cm){
    for(size_t j=b0;j<b1;j++)
        cd[j] = (unsigned char)((((int)(short)(Li[j]+Lo[j])<=(int)cap)) & (((int)(Li[j]<=thr)) | ((int)(Lo[j]<=cm))));
}
__attribute__((optimize("O3","tree-vectorize")))
static void mask16OrPlain(unsigned char* cd, const short* Li, const short* Lo,
                          size_t b0, size_t b1, short cap, short thr, short cm){
    for(size_t j=b0;j<b1;j++)
        cd[j] |= (unsigned char)((((int)(short)(Li[j]+Lo[j])<=(int)cap)) & (((int)(Li[j]<=thr)) | ((int)(Lo[j]<=cm))));
}
#if defined(__x86_64__) || defined(__i386__)
__attribute__((optimize("O3","tree-vectorize"),target("avx2")))
static void mask16AssignAVX2(unsigned char* cd, const short* Li, const short* Lo,
                             size_t b0, size_t b1, short cap, short thr, short cm){
    for(size_t j=b0;j<b1;j++)
        cd[j] = (unsigned char)((((int)(short)(Li[j]+Lo[j])<=(int)cap)) & (((int)(Li[j]<=thr)) | ((int)(Lo[j]<=cm))));
}
__attribute__((optimize("O3","tree-vectorize"),target("avx2")))
static void mask16OrAVX2(unsigned char* cd, const short* Li, const short* Lo,
                         size_t b0, size_t b1, short cap, short thr, short cm){
    for(size_t j=b0;j<b1;j++)
        cd[j] |= (unsigned char)((((int)(short)(Li[j]+Lo[j])<=(int)cap)) & (((int)(Li[j]<=thr)) | ((int)(Lo[j]<=cm))));
}
#endif
static MaskFn16 pickMask16A(){
#if defined(__x86_64__) || defined(__i386__)
    if(__builtin_cpu_supports("avx2")) return mask16AssignAVX2;
#endif
    return mask16AssignPlain;
}
static MaskFn16 pickMask16O(){
#if defined(__x86_64__) || defined(__i386__)
    if(__builtin_cpu_supports("avx2")) return mask16OrAVX2;
#endif
    return mask16OrPlain;
}
static MaskFn16 g_mask16A = pickMask16A();
static MaskFn16 g_mask16O = pickMask16O();

struct Sim {
    const Test* T;

    vector<vector<long long>> aE, aV;
    vector<long long> aSumV;
    vector<int> aHead, aTail, aCnt;
    int gpu = 0;
    int earlyStop = 0;
    vector<long long> arrTimes;
    vector<vector<int>> arrIds;
    int cap_ = 0;

    void init(const Test& t) {
        T = &t;

        cap_ = T->N + T->B + 2;
        aE.assign(T->K+1, vector<long long>(cap_));
        aV.assign(T->K+1, vector<long long>(cap_));
        aSumV.assign(T->K+1, 0);
        aHead.assign(T->K+1, 0); aTail.assign(T->K+1, 0); aCnt.assign(T->K+1, 0);
        kc.assign(T->K+1, KCst());
        kc2.assign(T->K+1, KC2());

        { int mLi=0,mLo=0; long long mSm=0;
          for(int i=1;i<=T->N;i++){ if(T->Lin[i]>mLi) mLi=T->Lin[i];
              if(T->Lout[i]>mLo) mLo=T->Lout[i];
              long long sm=(long long)T->Lin[i]+T->Lout[i]; if(sm>mSm) mSm=sm; }
          hiThr=mLi; hiCm=mLo; hiCap=(int)min(mSm,(long long)INT_MAX);
          use16 = (mSm<=32767); }
        map<long long,vector<int>> am;
        for(int i=1;i<=T->N;i++) am[T->Arr[i]].push_back(i);
        arrTimes.clear(); arrIds.clear();
        for(auto&kv:am){ arrTimes.push_back(kv.first); arrIds.push_back(kv.second); }
    }

    inline bool feasible(int i,int k,long long s,int& peakOut){
        int li=T->Lin[i], lo=T->Lout[i]; long long e=s+lo-1; int cap=T->M[k];
        if((long long)li+lo>cap) return false;
        int hd=aHead[k], tl=aTail[k], na=aCnt[k];
        if(na+1>T->B) return false;
        const long long* Ep=aE[k].data(); const long long* Vp=aV[k].data();
        long long sumV=aSumV[k];
        long long cnt=na, peak=0;
        for(int j=hd;j<tl;j++){
            long long C=Ep[j];
            if(C>=e) break;
            long long mem = sumV + C*cnt;
            long long add = li + (C - s + 1);
            if(mem + add > cap) return false;
            if(mem>peak) peak=mem;
            sumV-=Vp[j]; cnt--;
        }
        long long memE = sumV + e*cnt;
        if(memE + li + lo > cap) return false;
        if(memE>peak) peak=memE;
        peakOut=(int)peak; return true;
    }
    void place(int i,int k,long long s){
        int li=T->Lin[i], lo=T->Lout[i]; long long e=s+lo-1;
        long long v=(long long)li - s + 1;
        long long* Ep=aE[k].data(); long long* Vp=aV[k].data();
        int hd=aHead[k], tl=aTail[k];
        int pos=(int)(std::upper_bound(Ep+hd, Ep+tl, e) - Ep);
        for(int j=tl;j>pos;--j){ Ep[j]=Ep[j-1]; Vp[j]=Vp[j-1]; }
        Ep[pos]=e; Vp[pos]=v;
        aTail[k]=tl+1; aCnt[k]++; aSumV[k]+=v;
    }
    int chooseGpu(int i,long long s){
        if(T->K==1){ int peak; return feasible(i,1,s,peak) ? 1 : 0; }
        int best=-1; long long bestScore=LLONG_MAX;
        for(int k=1;k<=T->K;k++){ int peak; if(!feasible(i,k,s,peak)) continue;
            long long score = (gpu==0)? peak : (gpu==2? k : -(long long)peak);
            if(score<bestScore){bestScore=score;best=k;} }
        return best<0?0:best;
    }

    vector<int> pending;
    priority_queue<long long, vector<long long>, greater<long long>> compEv;

    vector<int> pLi, pLo, pSm;
    vector<unsigned char> cand;
    vector<int> placedPos;
    struct KCst { int thr, cm, cap; unsigned char full; };
    vector<KCst> kc;

    vector<short> qLi, qLo;
    struct KC2 { short thr, cm, cap; unsigned char full; };
    vector<KC2> kc2;
    int hiThr=0, hiCm=0, hiCap=0;
    bool use16=false;

    void buildSoA(){
        size_t P=pending.size();
        pLi.resize(P); pLo.resize(P); pSm.resize(P);
        for(size_t j=0;j<P;j++){ int i=pending[j]; int li=T->Lin[i], lo=T->Lout[i];
            pLi[j]=li; pLo[j]=lo;
            long long sm=(long long)li+(long long)lo;
            pSm[j] = sm>(long long)INT_MAX ? INT_MAX : (int)sm; }
    }
    void buildSoA2(){
        size_t P=pending.size();
        qLi.resize(P); qLo.resize(P);
        for(size_t j=0;j<P;j++){ int i=pending[j];
            qLi[j]=(short)T->Lin[i]; qLo[j]=(short)T->Lout[i]; }
    }

    inline void computeKC2(long long s){
        for(int k=1;k<=T->K;k++){ KC2& c=kc2[k]; int cap=T->M[k];
            c.cap = cap>hiCap ? (short)hiCap : (short)cap;
            c.full = (aCnt[k]+1 > T->B) ? (unsigned char)1 : (unsigned char)0;
            if(aCnt[k]==0){ c.cm=(short)hiCm; c.thr=(short)hiThr; }
            else{
                long long C0=aE[k][aHead[k]];
                long long cm=C0-s+1;
                long long thr=(long long)cap - aSumV[k] - C0*(long long)aCnt[k] - cm;
                c.cm  = cm >(long long)hiCm ? (short)hiCm : (short)cm;
                c.thr = thr<0 ? (short)-1 : (thr>(long long)hiThr ? (short)hiThr : (short)thr);
            } }
    }
    inline void computeMask2(size_t b0, size_t b1){
        bool first=true;
        for(int k=1;k<=T->K;k++){ const KC2& c=kc2[k]; if(c.full) continue;
            if(first){ g_mask16A(cand.data(), qLi.data(), qLo.data(), b0, b1,
                                 c.cap, c.thr, c.cm); first=false; }
            else g_mask16O(cand.data(), qLi.data(), qLo.data(), b0, b1,
                           c.cap, c.thr, c.cm); }
        if(first) memset(cand.data()+b0, 0, b1-b0);
    }

    inline void computeKC(long long s){
        for(int k=1;k<=T->K;k++){ KCst& c=kc[k]; c.cap=T->M[k];
            c.full = (aCnt[k]+1 > T->B) ? (unsigned char)1 : (unsigned char)0;
            if(aCnt[k]==0){ c.cm=INT_MAX; c.thr=INT_MAX; }
            else{
                long long C0=aE[k][aHead[k]];
                long long cm=C0-s+1;
                long long thr=(long long)c.cap - aSumV[k] - C0*(long long)aCnt[k] - cm;
                c.cm  = cm >(long long)INT_MAX ? INT_MAX : (int)cm;
                c.thr = thr<0 ? -1 : (thr>(long long)INT_MAX ? INT_MAX : (int)thr);
            } }
    }
    inline void computeMask(size_t b0, size_t b1){
        memset(cand.data()+b0, 0, b1-b0);
        for(int k=1;k<=T->K;k++){ const KCst& c=kc[k]; if(c.full) continue;
            g_maskKernel(cand.data(), pLi.data(), pLo.data(), pSm.data(), b0, b1,
                         c.cap, c.thr, c.cm); }
    }
    inline size_t nextCand(size_t j, size_t b1) const {
        const unsigned char* cd=cand.data();
        while(j<b1 && (j&7u)){ if(cd[j]) return j; ++j; }
        while(j+8<=b1){ uint64_t w; memcpy(&w,cd+j,8);
            if(w) return j+((size_t)__builtin_ctzll(w)>>3);
            j+=8;
        }
        while(j<b1){ if(cd[j]) return j; ++j; }
        return b1;
    }

    const vector<long long>* cumBound = nullptr;
    long long cumSlack = 0;
    vector<long long> cumD_rec;

    const vector<vector<long long>>* seedE = nullptr;
    const vector<vector<long long>>* seedV = nullptr;

    struct Ckpt {
        long long t, sumD; int launched;
        vector<vector<long long>> e, v;
        vector<int> rem;
    };
    bool ckRecord = false;
    int ckEvery = 0;
    vector<Ckpt>* ckOut = nullptr;
    const Ckpt* resumeCk = nullptr;
    const vector<int>* preS = nullptr;
    const vector<int>* preK = nullptr;
    const vector<long long>* preCumD = nullptr;

    long long run(const vector<double>& prio, long long bound, vector<int>& S, vector<int>& KK){
        for(int k=1;k<=T->K;k++){ aHead[k]=0; aTail[k]=0; aCnt[k]=0; aSumV[k]=0; }
        while(!compEv.empty()) compEv.pop();
        if(seedE){ for(int k=1;k<=T->K;k++){ const auto& se=(*seedE)[k]; const auto& sv=(*seedV)[k];
            int m=(int)se.size(); long long sv_sum=0;
            long long* Ep=aE[k].data(); long long* Vp=aV[k].data();
            for(int j=0;j<m;j++){ Ep[j]=se[j]; Vp[j]=sv[j]; sv_sum+=sv[j]; compEv.push(se[j]); }
            aTail[k]=m; aCnt[k]=m; aSumV[k]=sv_sum; } }
        S.assign(T->N+1,-1); KK.assign(T->N+1,-1);
        cumD_rec.assign(T->N+1, 0);
        pending.clear();
        bool soaValid=false;
        long long sumD=0, launched=0;
        size_t ai = 0;
        long long ckNext = 0;
        if(resumeCk){
            const Ckpt& c = *resumeCk;
            for(int k=1;k<=T->K;k++){ const auto& ce=c.e[k]; const auto& cv=c.v[k];
                int m=(int)ce.size(); long long sv_sum=0;
                long long* Ep=aE[k].data(); long long* Vp=aV[k].data();
                for(int j=0;j<m;j++){ Ep[j]=ce[j]; Vp[j]=cv[j]; sv_sum+=cv[j]; compEv.push(ce[j]); }
                aHead[k]=0; aTail[k]=m; aCnt[k]=m; aSumV[k]=sv_sum; }
            compEv.push(c.t);
            S = *preS; KK = *preK;
            for(int id : c.rem){ S[id]=-1; KK[id]=-1; }
            for(int j=0;j<=c.launched;j++) cumD_rec[j] = (*preCumD)[j];
            sumD = c.sumD; launched = c.launched;
            ai = arrTimes.size();
            pending = c.rem;
            auto cmp=[&](int a,int b){ if(prio[a]!=prio[b]) return prio[a]<prio[b]; return a<b; };
            std::sort(pending.begin(), pending.end(), cmp);
            if(sumD>bound) return LLONG_MAX;
            ckNext = ((launched/max(1,ckEvery))+1) * (long long)max(1,ckEvery);
        }

        while(launched < T->N){
            long long t;
            bool haveArr = ai < arrTimes.size();
            bool haveComp = !compEv.empty();
            if(!haveArr && !haveComp){
                if(pending.empty()) break;
                return LLONG_MAX;
            }
            if(haveArr && (!haveComp || arrTimes[ai] <= compEv.top())) t = arrTimes[ai];
            else t = compEv.top();
            while(!compEv.empty() && compEv.top()==t) compEv.pop();

            bool newArr=false; size_t oldSize=pending.size();
            if(haveArr && arrTimes[ai]==t){ for(int id:arrIds[ai]) pending.push_back(id); ai++; newArr=true; }

            if(pending.empty()) continue;
            long long s=t+1;

            for(int k=1;k<=T->K;k++){ const long long* Ep=aE[k].data(); const long long* Vp=aV[k].data();
                int hd=aHead[k], tl=aTail[k];
                while(hd<tl && Ep[hd]<s){ aSumV[k]-=Vp[hd]; aCnt[k]--; ++hd; }
                aHead[k]=hd; }
            if(newArr){
                auto cmp=[&](int a,int b){ if(prio[a]!=prio[b]) return prio[a]<prio[b]; return a<b; };
                std::sort(pending.begin()+oldSize, pending.end(), cmp);
                if(oldSize>0) std::inplace_merge(pending.begin(), pending.begin()+oldSize, pending.end(), cmp);
            }
            if(ckRecord && ckOut && launched >= ckNext && ai >= arrTimes.size()){
                ckOut->push_back(Ckpt());
                Ckpt& c = ckOut->back();
                c.t = t; c.sumD = sumD; c.launched = (int)launched;
                c.e.assign(T->K+1, {}); c.v.assign(T->K+1, {});
                for(int k=1;k<=T->K;k++){ int hd=aHead[k], tl=aTail[k];
                    c.e[k].assign(aE[k].begin()+hd, aE[k].begin()+tl);
                    c.v[k].assign(aV[k].begin()+hd, aV[k].begin()+tl); }
                c.rem = pending;
                ckNext = ((launched/max(1,ckEvery))+1) * (long long)max(1,ckEvery);
            }
            if(use16){

                size_t P=pending.size();
                if(!soaValid || newArr){ buildSoA2(); soaValid=true; }
                if(cand.size()<P) cand.resize(P);
                computeKC2(s);
                placedPos.clear();
                int consecFail=0;
                size_t computed=0, pi=0;
                size_t sb = earlyStop>0 ? (size_t)MASK_BLOCK_SIZE : (size_t)512;
                while(pi<P){
                    if(pi>=computed){
                        size_t nb=computed+sb; if(nb>P) nb=P;
                        computeMask2(computed, nb);
                        computed=nb;
                        sb=sb<<1; if(sb>512) sb=512;
                    }
                    size_t q=nextCand(pi,computed);
                    size_t zeros=q-pi;
                    if(earlyStop>0 && (long long)consecFail+(long long)zeros>=(long long)earlyStop)
                        break;
                    consecFail+=(int)zeros;
                    pi=q;
                    if(q>=computed) continue;
                    int i=pending[q];
                    int k=chooseGpu(i,s);
                    if(k>0){
                        place(i,k,s); S[i]=(int)s; KK[i]=k;
                        sumD += s - T->Arr[i]; launched++;
                        cumD_rec[launched]=sumD;
                        long long e=s+T->Lout[i]-1; compEv.push(e);
                        consecFail=0;
                        placedPos.push_back((int)q);
                        if(sumD>bound) return LLONG_MAX;
                        if(cumBound && sumD > (*cumBound)[launched] + cumSlack) return LLONG_MAX;
                        computeKC2(s);
                        if(q+1<computed) computeMask2(q+1,computed);
                    } else consecFail++;
                    pi=q+1;
                }
                if(!placedPos.empty()){
                    size_t w=(size_t)placedPos[0], np=placedPos.size();
                    int* pd=pending.data(); short* li=qLi.data(); short* lo=qLo.data();
                    for(size_t x=0;x<np;x++){
                        size_t from=(size_t)placedPos[x]+1;
                        size_t to=(x+1<np) ? (size_t)placedPos[x+1] : P;
                        size_t len=to-from;
                        if(len){
                            memmove(pd+w,pd+from,len*sizeof(int));
                            memmove(li+w,li+from,len*sizeof(short));
                            memmove(lo+w,lo+from,len*sizeof(short));
                            w+=len;
                        }
                    }
                    pending.resize(w); qLi.resize(w); qLo.resize(w);
                }
                continue;
            }
            size_t P=pending.size();
            if(!soaValid || newArr){ buildSoA(); soaValid=true; }
            if(cand.size()<P) cand.resize(P);
            computeKC(s);
            placedPos.clear();
            bool stopped=false;
            int consecFail=0;
            const size_t BLK=512;
            for(size_t b0=0; b0<P && !stopped; b0+=BLK){
                size_t b1=min(P,b0+BLK);
                computeMask(b0,b1);
                size_t pi=b0;
                while(pi<b1){
                    size_t q=nextCand(pi,b1);
                    size_t zeros=q-pi;
                    if(earlyStop>0 && (long long)consecFail+(long long)zeros>=(long long)earlyStop){
                        stopped=true; break;
                    }
                    consecFail+=(int)zeros;
                    if(q>=b1) break;
                    int i=pending[q];
                    int k=chooseGpu(i,s);
                    if(k>0){
                        place(i,k,s); S[i]=(int)s; KK[i]=k;
                        sumD += s - T->Arr[i]; launched++;
                        cumD_rec[launched]=sumD;
                        long long e=s+T->Lout[i]-1; compEv.push(e);
                        consecFail=0;
                        placedPos.push_back((int)q);
                        if(sumD>bound) return LLONG_MAX;
                        if(cumBound && sumD > (*cumBound)[launched] + cumSlack) return LLONG_MAX;
                        computeKC(s);
                        if(q+1<b1) computeMask(q+1,b1);
                    } else { consecFail++; }
                    pi=q+1;
                }
            }
            if(!placedPos.empty()){
                size_t w=(size_t)placedPos[0], np=placedPos.size();
                int* pd=pending.data(); int* li=pLi.data(); int* lo=pLo.data(); int* sm=pSm.data();
                for(size_t x=0;x<np;x++){
                    size_t from=(size_t)placedPos[x]+1;
                    size_t to=(x+1<np) ? (size_t)placedPos[x+1] : P;
                    size_t len=to-from;
                    if(len){
                        memmove(pd+w,pd+from,len*sizeof(int));
                        memmove(li+w,li+from,len*sizeof(int));
                        memmove(lo+w,lo+from,len*sizeof(int));
                        memmove(sm+w,sm+from,len*sizeof(int));
                        w+=len;
                    }
                }
                pending.resize(w); pLi.resize(w); pLo.resize(w); pSm.resize(w);
            }
        }
        if(launched<T->N) return LLONG_MAX;
        return sumD;
    }
};

static long long computeV(const Test& T, const vector<int>& S, long long& sumD_out){
    long long sumD=0, maxC=LLONG_MIN, maxD=LLONG_MIN;
    for(int i=1;i<=T.N;i++){ long long Di=S[i]-T.Arr[i]; sumD+=Di; maxD=max(maxD,Di);
        maxC=max(maxC,(long long)S[i]+T.Lout[i]); }
    sumD_out=sumD;
    return sumD+maxC+maxD;
}

static long long solveOffline(const Test& T, long long budgetMs, unsigned seed,
                              vector<int>& outS, vector<int>& outK,
                              const vector<vector<long long>>* seedE = nullptr,
                              const vector<vector<long long>>* seedV = nullptr) {
    Sim sim; sim.init(T); sim.gpu=0; sim.earlyStop=0;
    sim.seedE = seedE; sim.seedV = seedV;
    const bool initialBatch = (seedE == nullptr);
    auto mkprio2=[&](double linc,double w)->vector<double>{
        vector<double> p(T.N+1,0);
        for(int i=1;i<=T.N;i++) p[i]=linc*(double)T.Lin[i]*T.Lout[i] + w*(double)T.Lout[i]*T.Lout[i];
        return p;
    };
    auto mkprio=[&](double ac)->vector<double>{ return mkprio2(1000.0, ac); };

    auto t_start = chrono::steady_clock::now();
    auto elapsedMs=[&](){ return chrono::duration_cast<chrono::milliseconds>(chrono::steady_clock::now()-t_start).count(); };

    static const pair<double,double> GRID2D[] = {
        {1000,0},{1000,250},{1000,500},{1000,625},{1000,750},{1000,875},
        {1000,1000},{1000,1250},{1000,1500},{1000,2000},{1000,3000},
        {500,500},{500,1000},{500,2000},{500,4000},
        {250,250},{250,1000},{250,3000},{250,6000},
        {0,1000},{2000,500},
    };
    static const pair<double,double> GRID1D[] = {
        {1000,0},{1000,250},{1000,500},{1000,750},{1000,875},{1000,1250},
        {1000,2000},{1000,3000},{250,3000},{500,2000},
    };
    static const pair<double,double> GRIDMIN[] = {
        {1000,250},{1000,500},{1000,875},{1000,1500},{250,3000},
    };
    vector<double> bestPrio; long long bestSumD = LLONG_MAX; vector<int> bestS, bestK;
    int bestGpu = 0; int bestES = 0;

    static const int ESVALS_RESIDUAL[] = {24, 48, 96, 160, 224, 320};
    static const int ESVALS_INITIAL[]  = {16, 24, 48, 96, 160, 224, 320, 448};
    const int* ESVALS = initialBatch ? ESVALS_INITIAL : ESVALS_RESIDUAL;
    const int  NES    = initialBatch ? 8 : 6;
    pair<double,double> bestKey={1000,875};
    long long maxSimMsObserved = 1;
    {
        auto m0=elapsedMs();
        const double swfEff = SWEEP_FRACTION;
        long long sweepDeadline = (long long)(budgetMs*swfEff);
        sim.gpu=0; sim.earlyStop=32;
        { auto p=mkprio(875.0); vector<int> S,K; long long sd=sim.run(p,bestSumD,S,K);
          if(sd<bestSumD){bestSumD=sd;bestPrio=p;bestS=S;bestK=K;bestGpu=0;bestES=32;bestKey={1000,875};} }
        long long persim=max(1LL,(long long)(elapsedMs()-m0));
        if(elapsedMs()+persim<sweepDeadline){
            long long sm0=elapsedMs();
            vector<double> p(T.N+1,0);
            for(int i=1;i<=T.N;i++)
                p[i]=1000.0*(double)T.Lin[i]+250.0*(double)T.Lout[i];
            vector<int> S,K;
            long long sd=sim.run(p,bestSumD,S,K);
            persim=max(persim,elapsedMs()-sm0);
            if(sd<bestSumD){bestSumD=sd;bestPrio=p;bestS=S;bestK=K;bestGpu=0;bestES=32;}
        }
        long long affordable=(sweepDeadline)/persim;
        int nEs=NES;
        long long perEs=affordable/nEs;
        const pair<double,double>* G; int GN;
        if(perEs>=21){ G=GRID2D; GN=21; }
        else if(perEs>=14){ G=GRID1D; GN=10; }
        else if(perEs>=8){ G=GRIDMIN; GN=5; }
        else { G=GRIDMIN; GN=3; }
        sim.gpu=0;
        long long maxSimMs = persim;
        long long hardCap = budgetMs - 1;
        long long sweepRunDeadline = (affordable < 2*nEs) ? hardCap : sweepDeadline;
        for(int ei=0; ei<NES; ei++){ int es=ESVALS[ei]; sim.earlyStop=es;
            if(elapsedMs()>=sweepRunDeadline || elapsedMs()+maxSimMs>=hardCap) break;
            for(int gi=0;gi<GN;gi++){ double lc=G[gi].first, w=G[gi].second;
                if(es==0&&lc==1000.0&&w==875.0) continue;
                if(elapsedMs()>=sweepRunDeadline || elapsedMs()+maxSimMs>=hardCap) break;
                long long sm0=elapsedMs();
                auto p=mkprio2(lc,w); vector<int> S,K; long long sd=sim.run(p,bestSumD,S,K);
                maxSimMs=max(maxSimMs, elapsedMs()-sm0);
                if(sd<bestSumD){bestSumD=sd;bestPrio=p;bestS=S;bestK=K;bestGpu=0;bestES=es;bestKey={lc,w};}
            }
        }
        if(T.K>1){
            sim.earlyStop=bestES; auto bp = bestPrio.empty()? mkprio2(bestKey.first,bestKey.second) : bestPrio;
            for(int gmode : {1,2}){
                if(elapsedMs()>=sweepRunDeadline || elapsedMs()+maxSimMs>=hardCap) break;
                sim.gpu=gmode; vector<int> S,K;
                long long sm0=elapsedMs();
                long long sd=sim.run(bp,bestSumD,S,K);
                maxSimMs=max(maxSimMs, elapsedMs()-sm0);
                if(sd<bestSumD){bestSumD=sd;bestPrio=bp;bestS=S;bestK=K;bestGpu=gmode;} }
        }
        sim.gpu=bestGpu; sim.earlyStop=bestES;
        maxSimMsObserved = maxSimMs;

        {
            long long hc = budgetMs - 1;
            vector<double> bk = bestPrio; double kmax=0;
            for(int i=1;i<=T.N;i++) kmax=max(kmax,fabs(bk[i]));
            if(kmax<=0) kmax=1.0;
            const int    nBootP = BOOTSTRAP_PASSES;
            const double bootAl = BOOTSTRAP_ALPHA;
            for(int pass=0; pass<nBootP; pass++){
                if(elapsedMs()+maxSimMs>=hc) break;
                vector<int> Sc,Kc; long long sd=sim.run(bk,LLONG_MAX,Sc,Kc);
                if(sd==LLONG_MAX) break;
                if(sd<bestSumD){bestSumD=sd;bestPrio=bk;bestS=Sc;bestK=Kc;}
                long long maxD=0; for(int i=1;i<=T.N;i++) maxD=max(maxD,(long long)Sc[i]-T.Arr[i]);
                if(maxD<=0) break;
                for(int i=1;i<=T.N;i++){ long long d=(long long)Sc[i]-T.Arr[i];
                    bk[i] -= bootAl * ((double)d/(double)maxD) * kmax; }
            }
            sim.gpu=bestGpu; sim.earlyStop=bestES;
        }
    }

    if(bestS.empty()){ outS.clear(); outK.clear(); return LLONG_MAX; }

    long long lsDeadline = budgetMs - maxSimMsObserved;
    bool doLS = (elapsedMs() + maxSimMsObserved < lsDeadline);

    bool sfxMode = initialBatch;
    const long long slackDiv = sfxMode ? SFX_SLACK_DIVISOR : 45;
    const bool locSwap = sfxMode;
    const double fbEff = sfxMode ? SFX_BACK_BIAS : 0.0;
    vector<Sim::Ckpt> cks, cksTmp;
    if(sfxMode){ sim.ckEvery = max(16, T.N/max(1, CHECKPOINT_DIVISOR)); }

    vector<long long> bestCumD;
    long long persimLS = maxSimMsObserved;
    if(doLS){ vector<int> S,K; long long b0=elapsedMs();
        if(sfxMode){ sim.ckRecord=true; sim.ckOut=&cks; cks.clear(); }
        long long sd0 = sim.run(bestPrio, LLONG_MAX, S, K); bestCumD = sim.cumD_rec;
        sim.ckRecord=false; sim.ckOut=nullptr;
        persimLS = max(1LL, elapsedMs()-b0);
        if(sd0!=LLONG_MAX && sd0<bestSumD){ bestSumD=sd0; bestS=S; bestK=K; }
        if(sfxMode && cks.empty()) sfxMode=false; }

    long long estSimMs = maxSimMsObserved;
    long long estIters = sfxMode ? (persimLS>0 ? (lsDeadline - elapsedMs())/persimLS : 100000)
                                 : (estSimMs>0 ? (lsDeadline - elapsedMs())/estSimMs : 100000);
    int mA=50, mB=68, mC=86;
    if(estIters < 80){ mA=67; mB=100; mC=100; }
    else if(estIters < 300){ mA=60; mB=80; mC=92; }

    vector<int> order; for(int i=1;i<=T.N;i++) order.push_back(i);
    sort(order.begin(), order.end(), [&](int a,int b){ return bestS[a]<bestS[b]; });

    unsigned long long rng = 88172645463325252ULL ^ ((unsigned long long)seed<<32) ^ (unsigned long long)T.N;
    auto rnd=[&](){ rng^=rng<<13; rng^=rng>>7; rng^=rng<<17; return rng; };

    vector<int> S,K;
    long long accepts=0;

    auto refreshOrder=[&](){ for(int i=1;i<=T.N;i++) order[i-1]=i;
        sort(order.begin(),order.end(),[&](int a,int b){ return bestS[a]<bestS[b]; }); };
    auto areaOf=[&](int i){ return 1000.0*(double)T.Lin[i]*T.Lout[i] + 875.0*(double)T.Lout[i]*T.Lout[i]; };
    vector<int> delayed; delayed.reserve(T.N);
    auto refreshDelayed=[&](){ delayed.clear();
        for(int i=1;i<=T.N;i++) delayed.push_back(i);
        sort(delayed.begin(),delayed.end(),[&](int a,int b){
            long long da=bestS[a]-T.Arr[a], db=bestS[b]-T.Arr[b];
            if(da!=db) return da>db;
            return a<b;
        });
    };
    long long moveMinS = LLONG_MAX;
    auto touch=[&](int i){ if(bestS[i] < moveMinS) moveMinS = bestS[i]; };
    auto pickPos=[&](size_t n)->int{
        if(n==0) return 0;
        double u = (double)(rnd()%1000000)/1000000.0;
        if(fbEff>0) u = pow(u, 1.0+fbEff);
        else if(fbEff<0) u = pow(u, 1.0/(1.0-fbEff));
        int r=(int)(u*(double)n); if(r>=(int)n) r=(int)n-1; return r; };
    auto applyMove=[&](vector<double>& cand, int strong){
        if(!sfxMode){

            int moveType = (int)(rnd()%100);
            if(moveType<mA){
                int nmoves = (strong?2:1) + (int)(rnd()%3);
                for(int m=0;m<nmoves;m++){
                    int ai = (int)(rnd()%order.size());
                    int span = 1 + (int)(rnd()%24);
                    int bi = ai + (int)(rnd()%(2*span+1)) - span;
                    if(bi<0) bi=0;
                    if(bi>=(int)order.size()) bi=(int)order.size()-1;
                    std::swap(cand[order[ai]], cand[order[bi]]);
                }
            } else if(moveType<mB){
                int aj = (int)(rnd()%order.size());
                int span = 1 + (int)(rnd()%64);
                int bj = aj + 1 + (int)(rnd()%span);
                if(bj>=(int)order.size()) bj=(int)order.size()-1;
                int earlier=order[aj], later=order[bj];
                cand[later] = cand[earlier] - 0.5;
            } else if(moveType<mC){
                if(!delayed.empty()){
                    int topK = max(1,(int)(delayed.size()/6));
                    int reps = strong? (1+(int)(rnd()%2)) : 1;
                    for(int r=0;r<reps;r++){
                        int later = delayed[(int)(rnd()%topK)];
                        int aj = (int)((rnd()% (unsigned)order.size()));
                        aj = (int)((double)aj * 0.6);
                        int earlier = order[aj];
                        cand[later] = cand[earlier] - 0.5;
                    }
                }
            } else {
                int q = max(1,(int)(order.size()/4));
                int c1 = order[(int)(rnd()%q)], c2 = order[(int)(rnd()%q)];
                int big = (areaOf(c1)>=areaOf(c2))? c1 : c2;
                int half=(int)(order.size()/2);
                int bj = half + (int)(rnd()% (unsigned)max(1,(int)(order.size()-half)));
                if(bj>=(int)order.size()) bj=(int)order.size()-1;
                cand[big] = cand[order[bj]] + 0.5;
            }
            return;
        }
        const vector<int>& ord = order;
        const vector<int>& del = delayed;
        int moveType = (int)(rnd()%100);
        if(moveType<mA){
            int nmoves = (strong?2:1) + (int)(rnd()%3);
            int aiFixed = pickPos(ord.size());
            for(int m=0;m<nmoves;m++){
                int ai;
                if(locSwap){
                    ai = aiFixed + (int)(rnd()%49) - 24;
                    if(ai<0) ai=0;
                    if(ai>=(int)ord.size()) ai=(int)ord.size()-1;
                }
                else ai = pickPos(ord.size());
                int span = 1 + (int)(rnd()%24);
                int bi = ai + (int)(rnd()%(2*span+1)) - span;
                if(bi<0) bi=0;
                if(bi>=(int)ord.size()) bi=(int)ord.size()-1;
                touch(ord[ai]); touch(ord[bi]);
                std::swap(cand[ord[ai]], cand[ord[bi]]);
            }
        } else if(moveType<mB){
            int aj = pickPos(ord.size());
            int span = 1 + (int)(rnd()%64);
            int bj = aj + 1 + (int)(rnd()%span);
            if(bj>=(int)ord.size()) bj=(int)ord.size()-1;
            int earlier=ord[aj], later=ord[bj];
            touch(earlier); touch(later);
            cand[later] = cand[earlier] - 0.5;
        } else if(moveType<mC){
            if(!del.empty()){
                int topK = max(1,(int)(del.size()/6));
                int reps = strong? (1+(int)(rnd()%2)) : 1;
                for(int r=0;r<reps;r++){
                    int later = del[(int)(rnd()%topK)];
                    int aj = (int)((rnd()% (unsigned)ord.size()));
                    aj = (int)((double)aj * 0.6);
                    int earlier = ord[aj];
                    touch(earlier); touch(later);
                    cand[later] = cand[earlier] - 0.5;
                }
            }
        } else {
            int q = max(1,(int)(ord.size()/4));
            int c1 = ord[(int)(rnd()%q)], c2 = ord[(int)(rnd()%q)];
            int big = (areaOf(c1)>=areaOf(c2))? c1 : c2;
            int half=(int)(ord.size()/2);
            int bj = half + (int)(rnd()% (unsigned)max(1,(int)(ord.size()-half)));
            if(bj>=(int)ord.size()) bj=(int)ord.size()-1;
            touch(big); touch(ord[bj]);
            cand[big] = cand[ord[bj]] + 0.5;
        }
    };
    sim.cumBound = &bestCumD;
    sim.cumSlack = max<long long>(1, bestSumD / slackDiv);
    refreshDelayed();
    long long sinceImprove=0;
    while(doLS && (elapsedMs() < lsDeadline)){
        vector<double> cand = bestPrio;
        int strong = (sinceImprove > STALL_THRESHOLD) ? 1 : 0;
        moveMinS = LLONG_MAX;
        applyMove(cand, strong);
        if(strong) applyMove(cand, 1);
        long long sd;
        const Sim::Ckpt* rc = nullptr;
        if(sfxMode){

            for(int ci=(int)cks.size()-1; ci>=0; --ci)
                if(cks[ci].t < moveMinS){ rc = &cks[ci]; break; }
        }
        long long candidateBound = bestSumD;
        if(rc){
            sim.resumeCk = rc; sim.preS=&bestS; sim.preK=&bestK; sim.preCumD=&bestCumD;
            sim.ckRecord=true; sim.ckOut=&cksTmp; cksTmp.clear();
            sd = sim.run(cand, candidateBound, S, K);
            sim.resumeCk = nullptr; sim.ckRecord=false; sim.ckOut=nullptr;
        } else {
            if(sfxMode){ sim.ckRecord=true; sim.ckOut=&cksTmp; cksTmp.clear(); }
            sd = sim.run(cand, candidateBound, S, K);
            sim.ckRecord=false; sim.ckOut=nullptr;
        }
        bool improved = (sd < bestSumD);
        if(improved){
            bestSumD = sd; bestPrio.swap(cand); bestS=S; bestK=K;
            bestCumD = sim.cumD_rec;
            sim.cumSlack = max<long long>(1, bestSumD / slackDiv);
            accepts++; sinceImprove=0;
            if(rc){
                while(!cks.empty() && cks.back().t > rc->t) cks.pop_back();
                for(auto& c : cksTmp) cks.push_back(std::move(c));
            } else if(sfxMode){
                cks.swap(cksTmp);
            }
            if(accepts % 4 == 0){ refreshOrder(); refreshDelayed(); }
        } else { sinceImprove++; if(strong) sinceImprove=0; }
    }
    sim.cumBound = nullptr;

    outS = bestS; outK = bestK;
    long long bSumD; return computeV(T, bestS, bSumD);
}
}

namespace exact_smalln {

struct Solver {
    int N, M, B, Tcap, Hmax;
    std::vector<int> Lin, Lout;
    std::vector<long long> areaOf, prefAreaAll;
    long long maxLoutAll=0;
    std::vector<int> order;
    std::vector<std::vector<long long>> sufSortedArea;
    std::vector<long long> mem; std::vector<int> cnt;
    std::vector<int> S;
    long long bestV; std::vector<int> bestS; bool haveInc=false;
    std::vector<long long> tmpClb;
    long long deadline_ns; std::chrono::steady_clock::time_point t0;
    long long nodes=0; bool timedOut=false;

    inline bool feasible(int i,int s) const {
        int e=s+Lout[i]-1; if(e>Tcap) return false; int li=Lin[i];
        for(int t=s;t<=e;t++){ if(cnt[t]+1>B) return false;
            long long add=li+(long long)(t-s+1); if(mem[t]+add>M) return false; }
        return true;
    }
    inline void place(int i,int s){ int e=s+Lout[i]-1,li=Lin[i];
        for(int t=s;t<=e;t++){ mem[t]+=li+(long long)(t-s+1); cnt[t]++; } S[i]=s; }
    inline void unplace(int i,int s){ int e=s+Lout[i]-1,li=Lin[i];
        for(int t=s;t<=e;t++){ mem[t]-=li+(long long)(t-s+1); cnt[t]--; } S[i]=0; }

    inline bool wallUp(){ if(timedOut) return true; long long el=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-t0).count(); if(el>deadline_ns) timedOut=true; return timedOut; }
    int earliest(int i,int from){ if(timedOut) return -1; int s=from,g=0; while(s<=Tcap){ if(((++g)&255)==0 && wallUp()) return -1; if(feasible(i,s)) return s; s++; } return -1; }
    inline bool timeUp(){ if((nodes&255)==0){ long long el=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-t0).count(); if(el>deadline_ns) timedOut=true; } return timedOut; }

    void setup(){
        std::vector<long long> sa; for(int i=1;i<=N;i++) sa.push_back(areaOf[i]);
        std::sort(sa.begin(),sa.end());
        prefAreaAll.assign(N+1,0); for(int j=1;j<=N;j++) prefAreaAll[j]=prefAreaAll[j-1]+sa[j-1];
        maxLoutAll=0; for(int i=1;i<=N;i++) maxLoutAll=std::max(maxLoutAll,(long long)Lout[i]);
        order.resize(N); for(int i=0;i<N;i++) order[i]=i+1;
        std::sort(order.begin(),order.end(),[&](int a,int b){ if(areaOf[a]!=areaOf[b]) return areaOf[a]>areaOf[b]; return a<b; });
        sufSortedArea.assign(N+1,{});
        for(int d=N;d>=0;d--){ std::vector<long long> ar; for(int j=d;j<N;j++) ar.push_back(areaOf[order[j]]); std::sort(ar.begin(),ar.end()); sufSortedArea[d]=ar; }
    }

    long long lowerBound(long long curSumS,int depth,long long curMaxS,long long curMaxC){
        int rem=N-depth;
        const std::vector<long long>& ar=sufSortedArea[depth];
        tmpClb.assign(rem,0);
        { long long pref=0,cum=0; int c=0;
          for(int j=0;j<rem;j++){ pref+=ar[j];
              while(cum<pref && c<Tcap){ c++; long long r=M-mem[c]; if(r<0)r=0; cum+=r; }
              tmpClb[j]=c+1; } }

        { static thread_local std::vector<long long> ecs; ecs.clear();
          for(int j=depth;j<N;j++){ int i=order[j]; int es=earliest(i,1); if(es<0) return (long long)4e18; ecs.push_back((long long)es+Lout[i]); }
          std::sort(ecs.begin(),ecs.end());
          for(int k=0;k<rem;k++) if(ecs[k]>tmpClb[k]) tmpClb[k]=ecs[k]; }
        long long unplacedSumC=0, unplacedSumLout=0;
        for(int k=0;k<rem;k++) unplacedSumC+=tmpClb[k];
        for(int j=depth;j<N;j++) unplacedSumLout+=Lout[order[j]];
        long long lbSumS=curSumS+(unplacedSumC-unplacedSumLout);
        if(lbSumS<curSumS+rem) lbSumS=curSumS+rem;
        long long clbN=curMaxC; for(int k=0;k<rem;k++) clbN=std::max(clbN,tmpClb[k]);
        clbN=std::max(clbN,(prefAreaAll[N]+M-1)/M);
        long long lbMaxS=std::max(curMaxS,std::max(clbN-maxLoutAll,1LL));
        return lbSumS+clbN+lbMaxS;
    }

    void candidates(int i,int minStart,std::vector<int>& out){
        out.clear(); if(timedOut) return; int es=earliest(i,minStart); if(es<0) return;
        int hi=std::min(Tcap,Hmax-Lout[i]); int g=0;
        for(int s=es;s<=hi;s++){ if(((++g)&255)==0 && wallUp()) return; if(feasible(i,s)) out.push_back(s); }
    }

    void dfs(int depth,long long curSumS,long long curMaxS,long long curMaxC){
        nodes++; if(timeUp()) return;
        if(depth==N){ long long V=curSumS+curMaxC+curMaxS;
            if(!haveInc||V<bestV){ bestV=V; bestS=S; haveInc=true; if((long long)Hmax>bestV-1) Hmax=(int)(bestV-1); }
            return; }
        if(haveInc && lowerBound(curSumS,depth,curMaxS,curMaxC)>=bestV) return;
        int i=order[depth];
        int minStart=1;
        for(int j=0;j<depth;j++){ int k=order[j]; if(Lin[k]==Lin[i]&&Lout[k]==Lout[i]&&k<i) minStart=std::max(minStart,S[k]); }
        std::vector<int> cand; candidates(i,minStart,cand);
        for(int s:cand){
            long long nS=curSumS+s, nMaxS=std::max(curMaxS,(long long)s), nMaxC=std::max(curMaxC,(long long)s+Lout[i]);
            if(haveInc){ long long floor=nS+(N-depth-1)+std::max(nMaxC,1LL)+nMaxS; if(floor>=bestV) break; }
            place(i,s);
            if(!haveInc || lowerBound(nS,depth+1,nMaxS,nMaxC)<bestV) dfs(depth+1,nS,nMaxS,nMaxC);
            unplace(i,s);
            if(timedOut) return;
        }
    }

    void tryRecord(const std::vector<int>& sched){
        long long s=0,mS=0,mC=0; for(int i=1;i<=N;i++){ s+=sched[i]; mS=std::max(mS,(long long)sched[i]); mC=std::max(mC,(long long)sched[i]+Lout[i]); }
        long long V=s+mC+mS; if(!haveInc||V<bestV){ bestV=V; bestS=sched; haveInc=true; }
    }
    long long greedyBySeq(const std::vector<int>& seq,std::vector<int>& out){
        out.assign(N+1,0); std::fill(mem.begin(),mem.end(),0); std::fill(cnt.begin(),cnt.end(),0);
        long long s=0,mS=0,mC=0;
        for(int i:seq){ int st=earliest(i,1); if(st<0){ std::fill(mem.begin(),mem.end(),0); std::fill(cnt.begin(),cnt.end(),0); return -1; }
            place(i,st); out[i]=st; s+=st; mS=std::max(mS,(long long)st); mC=std::max(mC,(long long)st+Lout[i]); }
        for(int i:seq) if(out[i]) unplace(i,out[i]);
        return s+mC+mS;
    }
    void strongSeed(){
        if(wallUp()) return;
        std::vector<int> ids(N); for(int i=0;i<N;i++) ids[i]=i+1;
        auto tryseq=[&](std::function<bool(int,int)> cmp){ auto sq=ids; std::sort(sq.begin(),sq.end(),cmp); std::vector<int> out; long long V=greedyBySeq(sq,out); if(V>0) tryRecord(out); };
        tryseq([&](int a,int b){return areaOf[a]>areaOf[b];});
        tryseq([&](int a,int b){return areaOf[a]<areaOf[b];});
        tryseq([&](int a,int b){return Lout[a]>Lout[b];});
        tryseq([&](int a,int b){return Lout[a]<Lout[b];});
        tryseq([&](int a,int b){return Lin[a]>Lin[b];});
    }
    void localSearch(){
        if(!haveInc) return;
        std::vector<int> cur=bestS;
        std::fill(mem.begin(),mem.end(),0); std::fill(cnt.begin(),cnt.end(),0);
        for(int i=1;i<=N;i++) place(i,cur[i]);
        auto V=[&](){ long long s=0,mS=0,mC=0; for(int i=1;i<=N;i++){s+=cur[i];mS=std::max(mS,(long long)cur[i]);mC=std::max(mC,(long long)cur[i]+Lout[i]);} return s+mC+mS; };
        long long curV=V(); bool improved=true; int guard=0;
        while(improved && guard++<40 && !wallUp()){ improved=false;
            for(int i=1;i<=N;i++){ int olds=cur[i]; unplace(i,olds);
                int bi=olds; long long bv=curV; int hi=std::min(Tcap,Tcap); int g=0;
                for(int s=1;s<=hi;s++){ if(((++g)&255)==0 && wallUp()) break; if(!feasible(i,s)) continue; cur[i]=s;
                    long long ss=0,mS=0,mC=0; for(int j=1;j<=N;j++){ss+=cur[j];mS=std::max(mS,(long long)cur[j]);mC=std::max(mC,(long long)cur[j]+Lout[j]);}
                    long long v=ss+mC+mS; if(v<bv){ bv=v; bi=s; } }
                cur[i]=bi; place(i,bi); if(bv<curV){ curV=bv; improved=true; }
                if(timedOut) break; } }
        for(int i=1;i<=N;i++) unplace(i,cur[i]);
        tryRecord(cur);
    }
};

inline long long solve(const solv::Test& T, long long budgetMs,
                       const std::vector<int>& seedS, std::vector<int>& outS){
    Solver ex;
    ex.N=T.N; ex.M=T.M[1]; ex.B=(T.B<T.N?T.B:T.N);
    ex.Lin.assign(T.N+1,0); ex.Lout.assign(T.N+1,0); ex.areaOf.assign(T.N+1,0);
    long long sumLout=0;
    for(int i=1;i<=T.N;i++){ ex.Lin[i]=T.Lin[i]; ex.Lout[i]=T.Lout[i];
        ex.areaOf[i]=(long long)T.Lin[i]*T.Lout[i]+(long long)T.Lout[i]*(T.Lout[i]+1)/2; sumLout+=T.Lout[i]; }
    ex.Tcap=(int)(sumLout+T.N+8);
    ex.mem.assign(ex.Tcap+2,0); ex.cnt.assign(ex.Tcap+2,0); ex.S.assign(T.N+1,0);
    ex.setup();
    ex.deadline_ns=budgetMs*1000000LL; ex.t0=std::chrono::steady_clock::now();
    ex.bestV=LLONG_MAX;

    if((int)seedS.size()>=T.N+1){
        bool ok=true; for(int i=1;i<=T.N;i++) if(seedS[i]<1){ ok=false; break; }
        if(ok){
            std::fill(ex.mem.begin(),ex.mem.end(),0); std::fill(ex.cnt.begin(),ex.cnt.end(),0);
            int placedUpto=0;
            for(int i=1;i<=T.N;i++){ if(!ex.feasible(i,seedS[i])){ ok=false; break; } ex.place(i,seedS[i]); placedUpto=i; }
            for(int i=1;i<=placedUpto;i++) ex.unplace(i,seedS[i]);
            if(ok){ std::vector<int> sd(T.N+1,0); for(int i=1;i<=T.N;i++) sd[i]=seedS[i]; ex.tryRecord(sd); }
        }
    }

    ex.strongSeed();
    ex.localSearch();

    ex.Hmax = (ex.haveInc && ex.bestV-1 < ex.Tcap) ? (int)(ex.bestV-1) : ex.Tcap;
    ex.dfs(0,0,0,0);
    outS.assign(T.N+1,0);
    if(ex.haveInc) for(int i=1;i<=T.N;i++) outS[i]=ex.bestS[i];
    return ex.haveInc?ex.bestV:LLONG_MAX;
}

}

static char ibuf[1 << 16];
static int ipos = 0, ilen = 0;
static inline int gc() {
    if (ipos == ilen) { ilen = (int)read(0, ibuf, sizeof(ibuf)); ipos = 0; if (ilen <= 0) return -1; }
    return ibuf[ipos++];
}
static inline bool readLL(long long& x) {
    int c = gc();
    while (c != -1 && (c == ' ' || c == '\n' || c == '\r' || c == '\t')) c = gc();
    if (c == -1) return false;
    int sg = 1; if (c == '-') { sg = -1; c = gc(); }
    long long v = 0;
    while (c >= '0' && c <= '9') { v = v * 10 + (c - '0'); c = gc(); }
    x = v * sg; return true;
}

static vector<char> obuf;
static inline void oint_grow(long long x) {
    if (x == 0) { obuf.push_back('0'); return; }
    if (x < 0) { obuf.push_back('-'); x = -x; }
    char tmp[24]; int n = 0;
    while (x) { tmp[n++] = char('0' + x % 10); x /= 10; }
    while (n) obuf.push_back(tmp[--n]);
}

static char sbuf[1 << 18];
static int spos = 0;
static inline void sint(long long x) {
    if (x == 0) { sbuf[spos++] = '0'; return; }
    if (x < 0) { sbuf[spos++] = '-'; x = -x; }
    char tmp[24]; int n = 0;
    while (x) { tmp[n++] = char('0' + x % 10); x /= 10; }
    while (n) sbuf[spos++] = tmp[--n];
}
static inline void sch(char c) { sbuf[spos++] = c; }

static inline bool writeAll(const char* data, size_t len) {
    size_t off = 0;
    while (off < len) {
        ssize_t w = write(1, data + off, len - off);
        if (w < 0 && errno == EINTR) continue;
        if (w <= 0) return false;
        off += (size_t)w;
    }
    return true;
}

static const long long ALLATONCE_BUDGET_MS = 900;

static const int  EXACT_N_MAX        = 16;
static const long long EXACT_BUDGET_MS   = 350;
static const long long SMALL_EXACT_BASE_BUDGET_MS = 500;

static const long long SPREAD_RESID_TARGET_WALL = 900;
static const long long SPREAD_RESID_MIN_MS = 400;
static const long long SPREAD_RESID_MAX_MS = 750;
static std::chrono::steady_clock::time_point g_progStart;

static const long long QUADRATIC_WEIGHT = 875;

int main() {
    g_progStart = std::chrono::steady_clock::now();
    long long N, K, B;
    if (!readLL(N) || !readLL(K) || !readLL(B)) return 0;
    vector<int> M(K + 1, 0);
    for (int k = 1; k <= K; k++) { long long x; readLL(x); M[k] = (int)x; }

    long long t0, n0;
    if (!readLL(t0)) return 0;
    if (!readLL(n0)) return 0;

    vector<array<long long,4>> first; first.reserve((size_t)n0);
    for (long long j = 0; j < n0; j++) {
        long long id, li, lo, a;
        readLL(id); readLL(li); readLL(lo); readLL(a);
        first.push_back({id, li, lo, a});
    }

    if (t0 == 0 && n0 == N) {
        solv::Test T;
        T.N = (int)N; T.K = (int)K; T.B = (int)B;
        T.M.assign(K + 1, 0);
        for (int k = 1; k <= K; k++) T.M[k] = M[k];
        T.Lin.assign(N + 1, 0); T.Lout.assign(N + 1, 0); T.Arr.assign(N + 1, 0);
        for (auto& r : first) {
            int id = (int)r[0];
            T.Lin[id] = (int)r[1]; T.Lout[id] = (int)r[2]; T.Arr[id] = (int)r[3];
        }
        vector<int> S, Kk;

        bool useExact = ((int)K == 1 && (int)N <= EXACT_N_MAX && (int)N >= 1);
        long long baseBudget = useExact ? SMALL_EXACT_BASE_BUDGET_MS : ALLATONCE_BUDGET_MS;
        solv::solveOffline(T, baseBudget, 12345u, S, Kk);

        if (useExact) {

            long long baseSumD; long long baseV = solv::computeV(T, S, baseSumD);
            vector<int> exS;
            long long exV = exact_smalln::solve(T, EXACT_BUDGET_MS, S, exS);
            if (exV < baseV) {

                for (int i = 1; i <= (int)N; i++) { S[i] = exS[i]; Kk[i] = 1; }
            }
        }

        obuf.clear(); obuf.reserve((size_t)N * 16 + 16);
        oint_grow(N); obuf.push_back('\n');
        for (int i = 1; i <= (int)N; i++) {
            oint_grow(S[i]); obuf.push_back(' ');
            oint_grow((long long)i); obuf.push_back(' ');
            oint_grow(Kk[i]); obuf.push_back('\n');
        }
        if (!writeAll(obuf.data(), obuf.size())) return 0;

        return 0;
    }

    Sched sc;
    sc.init((int)N, (int)K, (int)B, M);
    sc.pol.quadraticWeight = QUADRATIC_WEIGHT;

    int esBase;
    {
        int es;
        if (N <= 500) es = 64;
        else { long long v = 64 + ((long long)N - 500) * 32 / 1000; if (v < 64) v = 64; if (v > 96) v = 96; es = (int)v; }
        sc.pol.earlyStop = es; esBase = es;
    }

    vector<int> Sid(N + 1, -1), Kid(N + 1, -1);
    long long arrivedCount = 0;

    auto recordDec = [&](const vector<Decision>& dec) {
        for (auto& d : dec) { Sid[d.id] = d.S; Kid[d.id] = d.k; }
    };

    auto emitDec = [&](const vector<Decision>& dec) {
        spos = 0;
        sint((long long)dec.size()); sch('\n');
        for (auto& d : dec) { sint(d.S); sch(' '); sint(d.id); sch(' '); sint(d.k); sch('\n'); }
        return writeAll(sbuf, (size_t)spos);
    };

    auto tryResidual = [&](long long t) -> bool {
        long long s0 = t + 1;

        vector<int> pend;
        for (int i = 1; i <= (int)N; i++) if (Sid[i] < 0) pend.push_back(i);
        int Mp = (int)pend.size();
        if (Mp < 2) return false;

        vector<vector<long long>> seedE((int)K + 1), seedV((int)K + 1);
        for (int i = 1; i <= (int)N; i++) {
            if (Sid[i] < 0) continue;
            long long e = (long long)Sid[i] + sc.Lout[i] - 1;
            if (e < s0) continue;
            int k = Kid[i];
            seedE[k].push_back(e);
            seedV[k].push_back((long long)sc.Lin[i] - Sid[i] + 1);
        }
        for (int k = 1; k <= (int)K; k++) {
            vector<size_t> idx(seedE[k].size());
            for (size_t j = 0; j < idx.size(); j++) idx[j] = j;
            sort(idx.begin(), idx.end(), [&](size_t a, size_t b){ return seedE[k][a] < seedE[k][b]; });
            vector<long long> ne(idx.size()), nv(idx.size());
            for (size_t j = 0; j < idx.size(); j++) { ne[j] = seedE[k][idx[j]]; nv[j] = seedV[k][idx[j]]; }
            seedE[k].swap(ne); seedV[k].swap(nv);
        }

        solv::Test R; R.N = Mp; R.K = (int)K; R.B = (int)B;
        R.M.assign((int)K + 1, 0); for (int k = 1; k <= (int)K; k++) R.M[k] = M[k];
        R.Lin.assign(Mp + 1, 0); R.Lout.assign(Mp + 1, 0); R.Arr.assign(Mp + 1, 0);
        vector<int> realId(Mp + 1, 0);
        for (int j = 0; j < Mp; j++) { int rid = pend[j]; realId[j + 1] = rid;
            R.Lin[j + 1] = sc.Lin[rid]; R.Lout[j + 1] = sc.Lout[rid]; R.Arr[j + 1] = (int)t; }

        long long residMs;
        {
            long long elapsed = (long long)std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - g_progStart).count();
            residMs = SPREAD_RESID_TARGET_WALL - elapsed;
            if (residMs > SPREAD_RESID_MAX_MS) residMs = SPREAD_RESID_MAX_MS;
            long long minEff = SPREAD_RESID_MIN_MS;
            if (residMs < minEff) residMs = minEff;

            if (elapsed >= SPREAD_RESID_TARGET_WALL) {
                long long em = 4LL * (long long)Mp; if (em < 50) em = 50;
                if (em < residMs) residMs = em;
            }
        }
        vector<int> rS, rK;
        long long Vresid = LLONG_MAX;
        solv::solveOffline(R, residMs, 12345u, rS, rK, &seedE, &seedV);
        if (!rS.empty()) {
            long long sd = 0, mc = LLONG_MIN, md = LLONG_MIN; bool ok = true;
            vector<int> S2(N + 1, -1);
            for (int i = 1; i <= (int)N; i++) S2[i] = Sid[i];
            for (int j = 1; j <= Mp; j++) { int rid = realId[j]; S2[rid] = rS[j]; }
            for (int i = 1; i <= (int)N; i++) {
                if (S2[i] < 0) { ok = false; break; }
                long long Di = S2[i] - sc.Arr[i]; sd += Di; if (Di > md) md = Di;
                if ((long long)S2[i] + sc.Lout[i] > mc) mc = (long long)S2[i] + sc.Lout[i];
            }
            if (ok) Vresid = sd + mc + md;
        }

        solv::Sim sg; sg.init(R); sg.gpu = 0; sg.earlyStop = esBase;
        sg.seedE = &seedE; sg.seedV = &seedV;
        vector<double> pk(Mp + 1, 0);
        for (int j = 1; j <= Mp; j++)
            pk[j] = 1000.0 * (double)R.Lin[j] * R.Lout[j]
                  + (double)sc.pol.quadraticWeight * (double)R.Lout[j] * R.Lout[j];
        vector<int> gS, gK; sg.run(pk, LLONG_MAX, gS, gK);
        long long Vgreedy = LLONG_MAX;
        {
            long long sd = 0, mc = LLONG_MIN, md = LLONG_MIN; bool ok = true;
            vector<int> Sf(N + 1, -1);
            for (int i = 1; i <= (int)N; i++) Sf[i] = Sid[i];
            for (int j = 1; j <= Mp; j++) { int rid = realId[j]; Sf[rid] = gS[j]; }
            for (int i = 1; i <= (int)N; i++) {
                if (Sf[i] < 0) { ok = false; break; }
                long long Di = Sf[i] - sc.Arr[i]; sd += Di; if (Di > md) md = Di;
                if ((long long)Sf[i] + sc.Lout[i] > mc) mc = (long long)Sf[i] + sc.Lout[i];
            }
            if (ok) Vgreedy = sd + mc + md;
        }

        const vector<int>* useS = nullptr; const vector<int>* useK = nullptr;
        long long useV = LLONG_MAX;
        if (Vgreedy != LLONG_MAX)                   { useV = Vgreedy; useS = &gS; useK = &gK; }
        if (Vresid  != LLONG_MAX && Vresid  < useV) { useV = Vresid;  useS = &rS; useK = &rK; }
        if (useS == nullptr) return false;

        vector<Decision> dec; dec.reserve(Mp);
        for (int j = 1; j <= Mp; j++) { int rid = realId[j]; dec.push_back({ (*useS)[j], rid, (*useK)[j] }); }
        if (!emitDec(dec)) return true;
        return true;
    };

    {
        vector<int> arr; arr.reserve(first.size());
        for (auto& r : first) {
            int id = (int)r[0];
            sc.Lin[id] = (int)r[1]; sc.Lout[id] = (int)r[2]; sc.Arr[id] = (int)r[3];
            arr.push_back(id);
        }
        arrivedCount += (long long)arr.size();
        vector<Decision> dec = sc.step(t0, arr);
        recordDec(dec);
        if (!emitDec(dec)) return 0;
    }
    if (sc.launchedCount == N) {

        long long t, ninp;
        while (readLL(t)) {
            if (!readLL(ninp)) break;
            for (long long j = 0; j < ninp; j++) { long long x; readLL(x); readLL(x); readLL(x); readLL(x); }
            const char* z = "0\n";
            if (!writeAll(z, 2)) return 0;
        }
        return 0;
    }

    vector<int> arr;
    long long t, ninp;
    while (readLL(t)) {
        if (!readLL(ninp)) break;
        arr.clear();
        for (long long j = 0; j < ninp; j++) {
            long long id, li, lo, a;
            readLL(id); readLL(li); readLL(lo); readLL(a);
            sc.Lin[(int)id] = (int)li; sc.Lout[(int)id] = (int)lo; sc.Arr[(int)id] = (int)a;
            arr.push_back((int)id);
        }
        arrivedCount += (long long)arr.size();

        if (arrivedCount == N && sc.launchedCount < N) {
            if (tryResidual(t)) {

                return 0;
            }

        }

        vector<Decision> dec = sc.step(t, arr);
        recordDec(dec);
        if (!emitDec(dec)) return 0;
        if (sc.launchedCount == N) break;
    }
    return 0;
}
