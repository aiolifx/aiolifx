"""Tests for address family selection and IPv6 address helpers."""

import socket

from aiolifx.aiolifx import address_family, mac_to_ipv6_linklocal


class TestAddressFamily:
    def test_ipv4_address(self):
        assert address_family("192.168.1.10") == socket.AF_INET

    def test_ipv4_loopback(self):
        assert address_family("127.0.0.1") == socket.AF_INET

    def test_ipv6_ula(self):
        # Thread devices are typically reachable at a ULA published
        # by the border router (OMR prefix).
        assert address_family("fd12:3456:789a:1:2:3:4:5") == socket.AF_INET6

    def test_ipv6_gua(self):
        assert address_family("2001:db8::1") == socket.AF_INET6

    def test_ipv6_loopback(self):
        assert address_family("::1") == socket.AF_INET6

    def test_ipv6_link_local_with_scope(self):
        assert address_family("fe80::d273:d5ff:fe01:0203%en0") == socket.AF_INET6

    def test_hostname_is_unspecified(self):
        # Hostnames must stay AF_UNSPEC so getaddrinfo can still pick
        # the family (e.g. a name that only resolves to an AAAA record).
        assert address_family("bulb.local") == socket.AF_UNSPEC

    def test_empty_string_is_unspecified(self):
        assert address_family("") == socket.AF_UNSPEC


class TestMacToIpv6LinkLocal:
    # EUI-64: flip the universal/local bit and insert fffe in the
    # middle of the MAC, so d0:73:d5:01:02:03 -> d273:d5ff:fe01:0203.
    EUI64 = "d273:d5ff:fe01:0203"

    def _addr(self, prefix):
        return mac_to_ipv6_linklocal("d0:73:d5:01:02:03", prefix)

    def test_default_prefix(self):
        # The documented default used to produce an invalid
        # triple-colon address ("fe80:::...").
        assert mac_to_ipv6_linklocal("d0:73:d5:01:02:03") == "fe80::" + self.EUI64

    def test_link_local_prefix_forms(self):
        # All conventional spellings of the link-local prefix work.
        for prefix in ("fe80", "fe80:", "fe80::"):
            assert self._addr(prefix) == "fe80::" + self.EUI64

    def test_full_64bit_prefix_without_trailing_colon(self):
        # The form documented by the CLI help (--ipv6prefix).
        assert self._addr("fd00:1:2:3") == "fd00:1:2:3:" + self.EUI64

    def test_full_64bit_prefix_with_trailing_colon(self):
        assert self._addr("fd00:1:2:3:") == "fd00:1:2:3:" + self.EUI64

    def test_short_prefix_is_zero_filled(self):
        # The README's "/48 prefix with a trailing colon" form.
        assert self._addr("fd00:1:2:") == "fd00:1:2::" + self.EUI64

    def test_compressed_prefix(self):
        assert self._addr("fd00::3") == "fd00::3:" + self.EUI64

    def test_all_forms_are_valid_ipv6(self):
        for prefix in (
            "fe80",
            "fe80:",
            "fe80::",
            "fd00:1:2:3",
            "fd00:1:2:3:",
            "fd00:1:2:",
            "fd00::3",
        ):
            addr = self._addr(prefix)
            socket.inet_pton(socket.AF_INET6, addr)
            assert address_family(addr) == socket.AF_INET6
