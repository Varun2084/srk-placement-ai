# College server setup (Docker) — SRK Placement AI

Is guide se college ka koi bhi ek computer **placement server** ban jaayega. Poora system (website + database) Docker mein chalta hai. Ek command se install ho jaata hai, aur power cut ya restart ke baad apne aap wapas chalu ho jaata hai.

---

## 1. Kya chahiye

| Cheez | Minimum | Behtar |
| --- | --- | --- |
| Computer | Koi bhi 64-bit desktop/laptop (i3 ya usse upar) | i5, SSD wala |
| RAM | 4 GB | 8 GB |
| Disk | 50 GB khaali | 100 GB+ SSD |
| Operating system | **Ubuntu 24.04 LTS** (free) | Ubuntu 24.04 LTS |
| Network | College LAN / Wi-Fi se juda ho | LAN cable |
| Power | — | UPS (power cut se data safe rahe) |

> Yeh computer din-raat chalu rehna chahiye. Iska use roz ke kaam ke liye na karein.
>
> College mein PC nahi hai? Yahi steps kisi bhi **cloud VPS** par bhi chalte hain (2 GB RAM, Ubuntu 24.04).

---

## 2. Ubuntu par install (recommended)

**Step 1 — Ubuntu install karein.** [ubuntu.com/download/desktop](https://ubuntu.com/download/desktop) se Ubuntu 24.04 LTS download karein, pendrive se install karein aur internet connect karein.

**Step 2 — Code laayein.** Do tareeke hain:

- **GitHub se** (repo private hai, isliye GitHub login ya token maangega):
  ```bash
  sudo apt install -y git
  git clone https://github.com/Varun2084/srk-placement-ai.git
  cd srk-placement-ai
  ```
- **Pendrive se:** GitHub par *Code → Download ZIP* karein, ZIP ko server par copy karein, unzip karein aur us folder mein jaayein.

**Step 3 — Ek command chalaayein.**

Pehle demo data ke saath chala kar dekhna ho (nakli students; management ko dikhane ke liye):
```bash
sudo bash deploy/install.sh
```

Asli students ke liye (khaali database):
```bash
sudo bash deploy/install.sh --real
```

Script yeh sab apne aap karti hai:
1. Docker install karti hai.
2. Strong passwords aur secret keys banati hai (`.env` file mein).
3. App aur database start karti hai. Pehli baar 5–10 minute lagte hain.
4. Har raat 2:30 baje database ka backup set karti hai.
5. End mein website ka address dikhati hai, jaise `http://192.168.1.50`.

`--real` mode mein admin ka email aur password screen par dikhega. Use likh lein, aur pehli login ke baad sidebar se **Change password** karein.

---

## 3. Website kaise kholein

College network (LAN/Wi-Fi) se judi kisi bhi computer ya phone ke browser mein server ka address kholein, jaise `http://192.168.1.50`.

**Address badalna nahi chahiye.** Router ki settings mein server ke liye *DHCP reservation / static IP* set karwa lein, warna router restart hone par IP badal sakta hai.

---

## 4. College ke bahar se access (optional, free HTTPS)

Students ghar se resume upload karein aur companies bahar se dekhein, iske liye **Cloudflare Tunnel** use karein. Isme static IP ya router mein port kholne ki zaroorat nahi.

1. College ka domain (jaise `srkgroup.in`) Cloudflare par add karein. Free plan kaafi hai.
2. Cloudflare dashboard mein jaayein: **Zero Trust → Networks → Tunnels → Create tunnel** (type *Cloudflared*).
3. Tunnel ka naam `srk-placement` rakhein. Wahan jo **token** dikhe, use copy karein.
4. Tunnel mein **Public hostname** jodein:
   - subdomain: `placement`, domain: `srkgroup.in`
   - service: `HTTP` → `app:8000`
5. Server par yeh command chalaayein:
   ```bash
   sudo bash deploy/install.sh --tunnel <YAHAN-TOKEN>
   ```

Ab site `https://placement.srkgroup.in` par HTTPS ke saath khulegi.

> Internet par kholne se pehle demo data hata dein (section 7) aur sabhi default passwords badal dein.

---

## 5. Pehla setup (asli use ke liye)

1. **Admin** se login karein → **Accounts** → TPO aur dono institutes ke coordinators ke accounts banayein. Har account ka temporary password screen par aayega; use privately share karein.
2. **Accounts → Download template** se CSV template lein. College record se students ki list bharein: naam, email, roll no, institute (`SRKCESM`/`SRKCP`), programme (`BTECH`, `DIPLOMA`, `MBA`, `BPHARM`, `DPHARM`), branch, passing year, CGPA/aggregate, backlogs, aur 18 se kam umar hai to `yes`.
3. CSV upload karein. Har student ka login password ek CSV file mein mil jaayega. Use students tak pahunchayein, phir woh file delete kar dein.
4. Students login karke privacy notice accept karein, resume upload karein aur password badlein.
5. TPO ya coordinator **Drives → New drive** se company ki drive banayein.

---

## 6. Roz ka kaam aur maintenance

| Kaam | Command (server par, `srk-placement-ai` folder mein) |
| --- | --- |
| Status dekhna | `sudo docker compose ps` |
| Logs dekhna | `sudo docker compose logs -f app` |
| Abhi backup lena | `sudo bash deploy/backup.sh` |
| Backups kahan hain | `backups/` folder (30 din tak rakhe jaate hain) |
| Naya version laana | `git pull && sudo docker compose up -d --build` |
| Band karna | `sudo docker compose stop` |
| Chalu karna | `sudo docker compose start` |

**Backup copy bahar rakhein.** Hafte mein ek baar `backups/` folder pendrive ya Google Drive par copy karein. Server ki disk kharab ho jaaye to bhi data bacha rahega.

**Backup se restore:**
```bash
gunzip -c backups/db-YYYYMMDD-HHMM.sql.gz | sudo docker compose exec -T db psql -U srk -d srk_placement
```

---

## 7. Demo se asli data par jaana

> ⚠️ Neeche wali command **saara data mita deti hai**: students, resumes, sab kuch. Sirf demo khatam karte waqt chalaayein.

```bash
sudo docker compose down -v      # demo database aur uploads delete
rm .env                          # purani settings hatao
sudo bash deploy/install.sh --real
```

---

## 8. Windows PC par (agar Ubuntu na ho sake)

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) install karein. Settings mein *Start Docker Desktop when you sign in* on karein.
2. Code ka folder kholein. `.env.example` ki copy banakar uska naam `.env` rakhein, aur usme `JWT_SECRET` (lamba random text) aur `POSTGRES_PASSWORD` badlein.
3. Us folder mein PowerShell kholkar chalaayein:
   ```powershell
   docker compose up -d --build
   ```
4. Browser mein `http://localhost` kholein. Doosre computers se `http://<is-PC-ka-IP>` kholein. Windows Firewall mein port 80 allow karna pad sakta hai.

Windows par automatic backup ke liye Task Scheduler mein `docker compose exec -T db pg_dump -U srk -d srk_placement > backup.sql` ka daily task bana lein.

---

## 9. Problem aaye to

| Problem | Hal |
| --- | --- |
| Website nahi khul rahi | `sudo docker compose ps` chalaayein; sab `running`/`healthy` hona chahiye. Phir `sudo docker compose logs app` dekhein. |
| Port 80 pehle se use mein hai | `.env` mein `APP_PORT=8080` karein, phir `sudo docker compose up -d`. Address ban jaayega `http://IP:8080`. |
| Doosre computer se nahi khulta | Dono ek hi network par hain? Server ka IP dobara check karein: `hostname -I` |
| Password bhool gaye | Coordinator ya TPO student page par **Reset password** kar sakte hain. Admin bhool jaaye to `.env` mein `ADMIN_PASSWORD` dekhein, ya developer se sampark karein. |
| Scanned (photo wala) resume upload nahi hota | Abhi sirf text wale PDF, DOCX ya TXT chalte hain. Student Word se "Save as PDF" karke upload kare. |
