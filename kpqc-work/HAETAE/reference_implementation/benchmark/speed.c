// SPDX-License-Identifier: MIT

#include <stdio.h>
#include <time.h>

#include "../include/randombytes.h"
#include "api.h"
#include "cpucycles.h"
#include "fft.h"
#include "ntt.h"
#include "params.h"
#include "polyfix.h"
#include "polymat.h"
#include "polyvec.h"
#include "speed_print.h"

#define NTESTS 1000

uint64_t t[NTESTS];

int main() {
  uint8_t vk[HAETAE_CRYPTO_PUBLICKEYBYTES], byte;
  uint8_t sk[HAETAE_CRYPTO_SECRETKEYBYTES];
  uint8_t sig[HAETAE_CRYPTO_BYTES];
  uint8_t msg[HAETAE_SEEDBYTES * 2];
  size_t siglen;
  int i = 0;
  clock_t srt, ed;
  clock_t overhead;
  polyvecm mat[HAETAE_K];
  polyfixvecl y1;
  polyfixveck y2;
  polyvecl vecl;
  polyvecm s1;
  polyveck s2;
  poly *a = &mat[0].vec[0];
  complex_fp32_16 fft_in[FFT_N];

  randombytes(msg, HAETAE_SEEDBYTES);
  overhead = clock();
  cpucycles();
  overhead = clock() - overhead;

  for (i = 0; i < NTESTS; ++i) {
    t[i] = cpucycles();
    polymatkm_expand_matA(mat, msg);
  }
  print_results("polymatkm_expand_matA:", t, NTESTS);

  for (i = 0; i < NTESTS; ++i) {
    t[i] = cpucycles();
    polyfixveclk_sample_hyperball(&y1, &y2, &byte, msg, i);
  }
  print_results("\npolyfixveclk_sample_hyperball:", t, NTESTS);

  for (i = 0; i < NTESTS; ++i) {
    t[i] = cpucycles();
    polyvecmk_expand_S(&s1, &s2, msg, i);
  }
  print_results("\npolyvecmk_uniform_eta:", t, NTESTS);

  for (i = 0; i < NTESTS; ++i) {
    t[i] = cpucycles();
    fft_init_and_bitrev(fft_in, &s2.vec[i % HAETAE_K]);
    fft(fft_in);
  }
  print_results("\nfft_bitrev + fft:", t, NTESTS);

  for (i = 0; i < NTESTS; ++i) {
    t[i] = cpucycles();
    ntt(&a->coeffs[0]);
  }
  print_results("\nntt:", t, NTESTS);

  for (i = 0; i < NTESTS; ++i) {
    t[i] = cpucycles();
    polymatkm_pointwise_montgomery(&s2, mat, &s1);
  }
  print_results("\npolymatkm_pointwise_montgomery:", t, NTESTS);

  for (i = 0; i < NTESTS; ++i) {
    t[i] = cpucycles();
    polyfixvecl_round(&vecl, &y1);
    polyfixveck_round(&s2, &y2);
  }
  print_results("\npolyfixvecl_round + polyfixveck_round:", t, NTESTS);

  for (i = 0; i < NTESTS; ++i) {
    t[i] = cpucycles();
    polyveck_poly_fromcrt(&s2, &s2, a);
  }
  print_results("\npolyveck_poly_fromcrt:", t, NTESTS);

  for (i = 0; i < NTESTS; ++i) {
    t[i] = cpucycles();
    polyveck_highbits_hint(&s2, &s2);
  }
  print_results("\npolyveck_highbits_hint:", t, NTESTS);

  srt = clock();
  for (i = 0; i < NTESTS; i++) {
    t[i] = cpucycles();
    crypto_sign_keypair(vk, sk);
  }
  ed = clock();
  print_results("\ncrypto_sign_keypair: ", t, NTESTS);
  printf("time elapsed: %.8fms\n\n", (double)(ed - srt - overhead * NTESTS) *
                                         1000 / CLOCKS_PER_SEC / NTESTS);

  srt = clock();
  for (i = 0; i < NTESTS; i++) {
    t[i] = cpucycles();
    crypto_sign_signature(sig, &siglen, sig, HAETAE_SEEDBYTES, NULL, 0, sk);
  }
  ed = clock();
  print_results("crypto_sign_signature: ", t, NTESTS);
  printf("time elapsed: %.8fms\n\n", (double)(ed - srt - overhead * NTESTS) *
                                         1000 / CLOCKS_PER_SEC / NTESTS);

  crypto_sign_signature(sig, &siglen, msg, HAETAE_SEEDBYTES, NULL, 0, sk);
  srt = clock();
  for (i = 0; i < NTESTS; i++) {
    t[i] = cpucycles();
    crypto_sign_verify(sig, siglen, msg, HAETAE_SEEDBYTES, NULL, 0, vk);
  }
  ed = clock();
  print_results("crypto_sign_verify: ", t, NTESTS);
  printf("time elapsed: %.8fms\n\n", (double)(ed - srt - overhead * NTESTS) *
                                         1000 / CLOCKS_PER_SEC / NTESTS);
  return 0;
}
