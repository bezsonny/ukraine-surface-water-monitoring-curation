import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from common import repair_semicolon_row,repair_text_date_autoconversion,repair_numeric_excel_serial

class TestParser(unittest.TestCase):
    def test_station_name_semicolon(self):
        parts=["27822","р. Дунай, 89,9 км, м. Ізмаїл, 89,9 км р. Дунай"," 1,0 км нижче м. Ізмаїл"]+[f"x{i}" for i in range(22)]+[""]
        fixed,meta=repair_semicolon_row(parts,24)
        self.assertEqual(len(fixed),24)
        self.assertEqual(fixed[1],"р. Дунай, 89,9 км, м. Ізмаїл, 89,9 км р. Дунай, 1,0 км нижче м. Ізмаїл")
        self.assertIsNotNone(meta)

    def test_text_date_dd_month(self):
        self.assertEqual(repair_text_date_autoconversion("15.Лип")[0],"15.07")
        self.assertEqual(repair_text_date_autoconversion("01.Тра")[0],"1.05")
        self.assertEqual(repair_text_date_autoconversion("12.Кві")[0],"12.04")

    def test_text_date_month_yy(self):
        self.assertEqual(repair_text_date_autoconversion("Лис.52")[0],"11.52")
        self.assertEqual(repair_text_date_autoconversion("Січ.99")[0],"1.99")

    def test_numeric_serial_ddmm(self):
        self.assertEqual(repair_numeric_excel_serial("45505","Nitrat","2024-08-13")[0],"1.08")

    def test_numeric_serial_mmyy(self):
        self.assertEqual(repair_numeric_excel_serial("20729","Nitrat","2024-08-13")[0],"10.56")

    def test_simazin_not_reinterpreted_as_date(self):
        self.assertEqual(repair_numeric_excel_serial("24000","Simazin","2005-01-17"),(None,None))

if __name__=="__main__":
    unittest.main()
