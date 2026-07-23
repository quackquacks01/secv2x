# HAETAE

HAETAE reference code (public release). Visit our [official website](https://www.kpqc.cryptolab.co.kr/haetae).

## Build

To build the HAETAE library and executables, there are the following prerequisites for KAT:

- [OpenSSL](https://www.openssl.org/)

Using cmake, you can build libraries and executables for each HAETAE mode.
The HAETAE modes are as follows: `haetae-mode2`, `haetae-mode3`, `haetae-mode5`

Build in the HAETAE directory.

```bash
$ cd <path_to_HAETAE>
$ cmake --preset <debug|release>
$ cmake --build --preset <debug|release>
```

## Run

If the build was successful, result files will be generated in the `build/<<debug|release>>/bin` directory.
To run each test, execute as follows.

```bash
$ cd build/<debug|release>/bin
$ ./haetae-mode2-main
$ ./haetae-mode2-benchmark
$ ./haetae-mode2-kat
```

## License

The codes and the specifications are under the MIT license.

## Acknowledgements

HAETAE is submitted to the Korean Post-Quantum Cryptography competition.
