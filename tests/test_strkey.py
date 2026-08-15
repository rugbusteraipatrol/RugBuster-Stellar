from rugbuster_stellar.strkey import is_valid_account_id


def test_known_stellar_account_id_is_valid():
    assert is_valid_account_id("GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN")


def test_bad_checksum_is_rejected():
    assert not is_valid_account_id("GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVA")

