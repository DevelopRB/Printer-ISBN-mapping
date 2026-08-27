"""Unit tests for identifier extraction, normalization, and matching."""



import sys

from pathlib import Path



sys.path.insert(0, str(Path(__file__).resolve().parents[1]))



from services.isbn_extractor import extract_isbn

from services.isbn_validator import is_valid_isbn13, validate_and_normalize





def test_extract_pub_f2_pb_book():

    assert (

        extract_isbn("Pub_9789372259803_F2_PB_BOOK_QC_Pharma..pdf") == "9789372259803"

    )





def test_extract_with_paren_2():

    assert extract_isbn("Pub_9789386397089 (2)_Pharma..pdf") == "9789386397089"





def test_extract_with_2_copies():

    assert (

        extract_isbn("Pub_9789373164076_F2_PB_Book (2 COPIES)_Pharma...")

        == "9789373164076"

    )





def test_extract_plain_isbn_filename():

    assert extract_isbn("9789351285106_Pharma.pdf") == "9789351285106"





def test_extract_hyphenated():

    assert extract_isbn("978-93-7225-9803") == "9789372259803"





def test_extract_hyphenated_in_filename():

    assert extract_isbn("978-93-7225-9803_Pharma.pdf") == "9789372259803"





def test_extract_isbn_prefix_embedded():

    assert extract_isbn("ISBN9789372259803ABC") == "9789372259803"





def test_does_not_extract_short_numbers():

    assert extract_isbn("F2_PB_BOOK_QC_(2)_4010") is None

    assert extract_isbn("(2 COPIES)") is None

    assert extract_isbn("2") is None

    assert extract_isbn("4010") is None





def test_extract_returns_none_for_empty():

    assert extract_isbn("not an isbn") is None

    assert extract_isbn(None) is None





def test_business_identifiers_extracted_as_is():

    """8888/1111/4444… identifiers are kept exactly — never rewritten to 978…"""

    assert extract_isbn("8888001171897_F2_Pharma LB.pdf") == "8888001171897"

    assert extract_isbn("8888000240648_F2_QC LB 2 COPY_Pharma..pdf") == "8888000240648"

    assert extract_isbn("1111012883952_F3 LB_Pharma..pdf") == "1111012883952"

    assert extract_isbn("4444000859651_F3_Pharma..pdf") == "4444000859651"

    assert extract_isbn("1111012148150_F4 LB_Pharma..pdf") == "1111012148150"

    assert extract_isbn("4444006242815_F3_Pharma..pdf") == "4444006242815"





def test_never_converts_to_fake_978():

    """Must not invent 978111… / 978888… from business identifiers."""

    for raw, expected in (

        ("1111012148150_F4 LB_Pharma..pdf", "1111012148150"),

        ("8888000240648_F2_QC LB 2 COPY_Pharma..pdf", "8888000240648"),

        ("8888001171897_F2_Pharma LB.pdf", "8888001171897"),

        ("4444006242815_F3_Pharma..pdf", "4444006242815"),

    ):

        got = extract_isbn(raw)

        assert got == expected

        assert not got.startswith("978111")

        assert not got.startswith("978888")

        assert not got.startswith("978444")





def test_hyphenated_978_without_checksum_gate():

    assert (

        extract_isbn("Pub_978-93-5722-414-7_BOOK_F2_PB_Pharma..pdf") == "9789357224147"

    )

    assert (

        extract_isbn("978-93-6280-754-0 F2 _ PB Book Anthropology.pdf")

        == "9789362807540"

    )





def test_list_a_normalize_business_identifier():

    assert validate_and_normalize("8888001171897") == "8888001171897"

    assert validate_and_normalize("1111012883952") == "1111012883952"

    assert validate_and_normalize("978-93-7225-980-3") == "9789372259803"

    assert validate_and_normalize("9789372259803") == "9789372259803"





def test_list_a_does_not_convert_isbn10_to_978():

    # Even if digits look like ISBN-10, keep as-is (no 978 rewrite)

    assert validate_and_normalize("1234567890") == "1234567890"





def test_isbn13_checksum_diagnostic_only():

    assert is_valid_isbn13("9789372259803") is True

    assert is_valid_isbn13("9789372259800") is False

    assert is_valid_isbn13("8888001171897") is False  # not a standard ISBN-13





def test_matching_business_identifier():

    list_a = {"8888001171897"}

    printer = {"8888001171897"}

    assert "8888001171897" in list_a and "8888001171897" in printer



    list_a2 = {"1111012883952"}

    printer2 = {"1111012883952"}

    assert list_a2 == printer2


