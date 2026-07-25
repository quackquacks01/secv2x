#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <stddef.h>
#include <stdint.h>

#include "api.h"
#include "common/rng.h"

#ifndef AIMER_EXPORT
#define AIMER_EXPORT __declspec(dllexport)
#endif

static INIT_ONCE g_rng_once = INIT_ONCE_STATIC_INIT;

static BOOL CALLBACK initialize_rng_once(
    PINIT_ONCE init_once,
    PVOID parameter,
    PVOID *context
) {
    unsigned char entropy[48];
    NTSTATUS status;

    (void)init_once;
    (void)parameter;
    (void)context;

    status = BCryptGenRandom(
        NULL,
        entropy,
        (ULONG)sizeof(entropy),
        BCRYPT_USE_SYSTEM_PREFERRED_RNG
    );
    if (status < 0) {
        return FALSE;
    }

    randombytes_init(entropy, NULL, 256);
    SecureZeroMemory(entropy, sizeof(entropy));
    return TRUE;
}

static int ensure_rng_initialized(void) {
    return InitOnceExecuteOnce(
        &g_rng_once,
        initialize_rng_once,
        NULL,
        NULL
    ) ? 0 : -1;
}

AIMER_EXPORT size_t kpqc_aimer_128f_publickeybytes(void) {
    return CRYPTO_PUBLICKEYBYTES;
}

AIMER_EXPORT size_t kpqc_aimer_128f_secretkeybytes(void) {
    return CRYPTO_SECRETKEYBYTES;
}

AIMER_EXPORT size_t kpqc_aimer_128f_signaturebytes(void) {
    return CRYPTO_BYTES;
}

AIMER_EXPORT int kpqc_aimer_128f_keypair(uint8_t *pk, uint8_t *sk) {
    if (ensure_rng_initialized() != 0) {
        return -2;
    }
    return crypto_sign_keypair(pk, sk);
}

AIMER_EXPORT int kpqc_aimer_128f_signature(
    uint8_t *sig,
    size_t *siglen,
    const uint8_t *message,
    size_t message_len,
    const uint8_t *context,
    size_t context_len,
    const uint8_t *sk
) {
    if (ensure_rng_initialized() != 0) {
        return -2;
    }
    return crypto_sign_signature(
        sig,
        siglen,
        message,
        message_len,
        context,
        context_len,
        sk
    );
}

AIMER_EXPORT int kpqc_aimer_128f_verify(
    const uint8_t *sig,
    size_t siglen,
    const uint8_t *message,
    size_t message_len,
    const uint8_t *context,
    size_t context_len,
    const uint8_t *pk
) {
    return crypto_sign_verify(
        sig,
        siglen,
        message,
        message_len,
        context,
        context_len,
        pk
    );
}
