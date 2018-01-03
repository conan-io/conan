#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan  3 15:39:35 2018

@author: weatherill
"""

import unittest
import gnupg
import tarfile
import os
from conans.errors import ConanException


from conans.client.tools.files import verify_gpg_sig

passphrase = "test_key"
test_message_contents = "test message"

fingerprint = "9CA0A9A040F911A9468706DABAE58647546E350C"

GPG_PUBLIC_KEY = """
-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v1

mQENBFpM+mQBCADbqdhrLp+QcXfoJdiyQr6xquZcedPgh1n1XTNw1FNNK7Bylos2
oA+QhyxgnSCWpDzSI1fM3vhqb9AMEVS5HFBddYCtGS1BPlk4HHPnM8hw76J1T88n
yLcMXgj1eFIIt+HJstNtlaeOSlvnMYZPjE5uZi+iZpeDgjoR6Pa/yVXo/NnxcCSH
MWTHzU/JarY24sbzb7aaDCyk61+B4O6Kpyf0t8mJ1cqtsmsg8EK/Jzni1+AzfZqx
hfREW12bqx7VjKX9SiAbgmuMkdrgFjI32i2pWI9rZjabm6b5DB9uRTMqnKe9FvvP
9ppqrWOVWdl1pHVISgbLOr8CdVsWveTPtde3ABEBAAG0Lk1yLiBUZXN0IChNci4g
VGVzdCdzIFRlc3Qga2V5KSA8dGVzdEB0ZXN0LmNvbT6JATgEEwECACIFAlpM+mQC
GwMGCwkIBwMCBhUIAgkKCwQWAgMBAh4BAheAAAoJELrlhkdUbjUMFxQIANN//2Ca
LfWA1crP/7R6yub017bKfx+1VKK6G5jrQs1wpczkPlD27A359xqDlZAl8gyqiBdT
tfw+6sPGiaK+tIn8CIko2IKOPCBVpwUOR/1ETlTEW8a9lHOdRE91gNXXi71IyTIH
xo2TJT61diAM8m8QZAMccue6LCpWU64+U3XcOEVH2cYqin6+5ejPFcBwOrWJCPfk
EYGjhdGu/cAiKn99Ln2ADWRvHwdH7MkN598HiJcOJn8JUUvQvImxCs007E3wRU/a
Mo1PLV83yRttnB4PTUDFUsJ0ftJEltB02aFT1M5AbRWuNN3LjXivMjSU57L5mHuH
HJcBXRz/93Ps8/+5AQ0EWkz6ZAEIAL0RqFuzWaf2JFE3YYT+nOmFdYjeXLCuoHca
ei2i17lb5ovpyg42s6W0X7iHePH819e+sDCiC5cHCR9Jq4wRgSHgVbOEVYpGOCJS
JthXkxXW9B7Tovx4LxnBPMCerYKO5seTZsqGuAM1OFFJCfrMrsyCugtcG4vdmcJ9
vx5dnAiU1B/Q0x5Zrf54U6BR4txchUlp5YVZY+LYePFOAW++IV4Dqz0BKxuDeTsp
uQsjnq0oZs6pL/iYDyVdJ6CvyWkcYh0G9qKsUvbx1yv/vBZScEnMLu1mAP4IjE/L
XiI83LwYRw7sd6PvCtWrG+zdyi1TLTk38TAgLgwGPAjbSxT6AdsAEQEAAYkBHwQY
AQIACQUCWkz6ZAIbDAAKCRC65YZHVG41DB8ICAC71I03uSElanBj7Qo5eXfNylO3
gvpGnHex0ckNJR1ie1fGFTdw094as3azIWXu2s+NoamFZvZXRDmJO3Kr59zp1KTK
SfeUvHAdEn4suXC9bhxuLlva/KYCWZisDGeXQ9KQbFQsIACOnAgdjuukwUZV2MvU
J17v/OTO/Le2wHawP86Yu9EADeJ3e4uE0d9VWs9qV8XqTdM6pWdCAxd/YEVN4fzw
BjqCy1JnG11UTAAR1WYrl9bM3GOhIZzOUI1c9feKiGBF90iGPvhLr+EmRZ9oHzo9
M6uKwHV05mxeB62wpsyovvLNmv+qmQ0tunZ2OJnDd6sC3GBFVRMxitUXU5KS
=j70v
-----END PGP PUBLIC KEY BLOCK-----
"""

GPG_PRIVATE_KEY = """
-----BEGIN PGP PRIVATE KEY BLOCK-----
Version: GnuPG v1

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
=lmU2
-----END PGP PRIVATE KEY BLOCK-----
"""


def generate_test_data(basename):
    outfiles = []
    
    #create text file
    with open(basename + ".txt", "w") as f:
        f.write(test_message_contents)
        f.write('\n')
    
    outfiles.append(basename+".txt")
    
    #create binary file
    with tarfile.TarFile(basename + ".tar.gz", "w") as f:
        f.add(basename+".txt")
    
    outfiles.append(basename + ".tar.gz")
    
    #import private key
    _gpg = gnupg.GPG(gnupghome="./keys")
    _gpg.import_keys(GPG_PRIVATE_KEY)    
    _gpg.import_keys(GPG_PUBLIC_KEY)
    
    outfiles.append("./keys")
    
    if len(_gpg.list_keys(keys=fingerprint)) == 0:
        raise RuntimeError("importing GPG keys failed")


    #sign binary file detached signature
    with open(basename + ".tar.gz") as f:
        signed = _gpg.sign_file(f,keyid=fingerprint[-8:],passphrase=passphrase,
                                detach=True,binary=True,
                                output=basename+".tar.gz.sig")
    
    if not signed:
        raise RuntimeError("failed to sign test data")
    
    outfiles.append(basename + ".tar.gz.sig")

    #delete private and public keys
    deleted_priv = _gpg.delete_keys(fingerprint, secret=True)
    if not deleted_priv:
        raise RuntimeError("failed to delete private key: %s" 
                           % deleted_priv.status)

    deleted_pub = _gpg.delete_keys(fingerprint)
    if not deleted_pub:
        raise RuntimeError("failed to delete public key: %s " 
                           % deleted_pub.status)

    return outfiles, _gpg



class GPGVerifyTest(unittest.TestCase):
    def setUp(self):
        self._data_files, self._gpg = generate_test_data("gpg_test_data")
        self._data_file = "gpg_test_data.tar.gz"
        self._sig_file = "gpg_test_data.tar.gz.sig"
    
    
    def tearDown(self):        
        map(os.remove,self._data_files)

    def testCorrectVerifyFile(self):
        verify_gpg_sig(data_file=self._data_file, pubkey=GPG_PUBLIC_KEY,
                       sig_file=self._sig_file)
        
        #if we got to here without throwing, verification completed

    def testIncorrectVerifyFile(self):
        with self.assertRaises(ConanException):
            verify_gpg_sig(data_file=self._data_file,pubkey=GPG_PUBLIC_KEY,
                           sig_file=self._sig_file)


if __name__ == "__main__":
    unittest.main()