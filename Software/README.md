# Ribbon Cable Tester - Phan mem dieu khien (PySide6)

Phan mem GUI de dieu khien board test cap ribbon 80-pin (10x 74HC595 + 10x 74HC165)
qua UART, ho tro nhieu profile cap (so pin, nhieu dau connector, bypass pin, anh xa
pin tuy y giua cac dau cap), hien thi truc quan ket qua PASS/OPEN/SHORT, va xuat
bao cao CSV.

## Cai dat

```bash
pip install -r requirements.txt
```

## Chay chuong trinh

```bash
python main.py
```

## Cau truc thu muc

```
cable_tester_app/
  main.py              - diem khoi chay
  main_window.py        - cua so chinh, 2 tab
  cable_setup_page.py   - tab thiet lap cau hinh cap (profile)
  test_run_page.py      - tab chay test + hien thi ket qua + xuat CSV
  connector_view.py     - widget ve luoi pin connector, click duoc, to mau
  models.py             - CableProfile / ConnectorSpec / WireMapping (luu file .json)
  uart_comm.py          - giao tiep Serial voi board (chay tren thread rieng)
  profiles/             - noi luu cac file profile .json
    example_64_to_2x34.json  - profile mau: cap 64-pin sang 2 dau 34-pin
  reports/               - noi luu bao cao CSV xuat ra (tu tao khi xuat lan dau)
```

## Quy trinh su dung

### 1. Tab "Thiet lap cap (Cable Setup)"
1. Dat ten cap, chon so pin cho Connector A.
2. Bam "+ Them connector B" de them tung dau connector con lai cua cap (co the them
   nhieu lan neu cap co nhieu dau, vi du 2 dau 34-pin).
3. Click 1 pin tren Connector A, roi click pin tuong ung ben Connector B de tao 1
   soi day (moi soi day se duoc tu dong gan 1 "board pin" tren 80 pin cua board).
4. Pin nao khong dung toi (vi du 2 chan thua cua connector 34-pin) thi khong ghep -
   no se tu dong khong nam trong active-mask khi test (khong can thao tac gi them,
   chi can KHONG tao wire cho pin do).
5. Bam "Luu profile" - luu vao thu muc `profiles/` (mac dinh) hoac noi ban chon.

### 2. Tab "Chay test (Run Test)"
1. Chon profile cap can test tu danh sach.
2. Chon cong COM va baudrate (mac dinh 115200, khop firmware).
3. Bam "Chay Test" - phan mem gui lenh `T:<hexmask>` xuong board (chi cac pin co
   trong profile moi duoc quet), nhan JSON ket qua, to mau truc tiep len so do
   connector: xanh la = PASS, do = OPEN, vang = SHORT.
4. Bam "Xuat bao cao CSV" de luu ket qua kem thoi gian test.

## Giao thuc UART (tham khao firmware `cable_tester_80pin.ino`)

- PC gui: `T:<20 ky tu hex>\n` - 20 hex = 80 bit active-mask (bit=1: pin can quet).
- Board tra ve 1 dong JSON: `{"open":[7,15],"short":[[1,2]]}` (pin 1-based).

## Ghi chu

- Thu tu "lien ke" dung de phat hien SHORT giua 2 pin la theo **chi so board pin
  lien tiep** (1,2,3...), gia dinh viec dau day tu board ra connector test la
  tuan tu, khong dao thu tu. Neu mach that co dao thu tu, can dieu chinh lai vi
  tri dau day vat ly cho khop, thuat toan phan mem/firmware khong thay doi.
- File profile la JSON thuan, co the chinh sua tay hoac dung lam template de tao
  nhanh profile moi (xem `profiles/example_64_to_2x34.json`).
