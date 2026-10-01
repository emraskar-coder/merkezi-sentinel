# 🛡️ Merkezi Sentinel — Otonom Filo Canlılık ve Sağlık Gözcüsü

Ekosistemdeki mevcut **62 projenin ve bundan sonra eklenecek tüm yeni projelerin** hiçbir aksamaya uğramadan, stabil ve sağlıklı bir şekilde çalışmasını sağlayan otonom canlılık ve çıktı gözcüsüdür.

---

## 🎯 Çözülen Temel Problem (Sessiz Ölümlerin Sonu)

Geliştirdiğimiz otomasyon ve botlarda en büyük tehlike hatanın çıkması değil, **hatanın sessizce kalmasıdır (Silent Failure)**:
* **Örnek 1 (LinkedIn Vakası):** Railway deploy "SUCCESS" gösterir, Typefully'ye taslak yüklenir; fakat SMTP port engeli yüzünden onay maili iletilemez. Sistem 1 hafta boyunca sessizce bekler.
* **Örnek 2 (Takalike Chatbot Vakası):** Bot ayakta görünür ama webhook endpoint'i 404/500 döner veya Meta/ManyChat token'ı düşer; kullanıcı mesajları havada kalır.
* **Örnek 3 (ePosta Asistanı Vakası):** Zamanlanmış cron çalışmaz, sabah özeti üretilmez ve kimse fark etmez.

**Merkezi Sentinel**, "sunucu ayakta mı?" yüzeysel sorusu yerine **"Beklenen iş çıktısı gerçekten üretildi mi, yerine ulaştı mı ve token'lar taze mi?"** derin denetimini yapar.

---

## 🏗️ 4 Katmanlı Otonom Denetim Mimarisi

```
┌─────────────────────────────────────────────────────────────┐
│             MERKEZİ SENTINEL GÖZCÜ MOTORU                   │
├─────────────────────────────────────────────────────────────┤
│ 1. OTOMATİK KEŞİF (Auto-Discovery Engine)                   │
│    Projeler/ altındaki tüm projeleri otomatik tanır.        │
│    Hiçbir manuel dosya düzenlemesine gerek yoktur.          │
├─────────────────────────────────────────────────────────────┤
│ 2. UÇTAN UCA ÇIKTI KONTROLÜ (Deliverable Verification)      │
│    • LinkedIn: Typefully'de yetim/onaysız taslak var mı?    │
│    • ePosta: Bugünün sabah özeti üretildi mi?               │
│    • Video/İçerik: Çıktı klasöründe taze hareket var mı?    │
├─────────────────────────────────────────────────────────────┤
│ 3. CANLILIK & WEBHOOK KONTROLÜ (Health & Integrations)      │
│    • Takalike & Webhook: /health endpoint HTTP 200 mü?      │
│    • ManyChat & Meta: API token aktif ve yetkili mi?        │
│    • Notion & Typefully: API erişimi çalışıyor mu?          │
├─────────────────────────────────────────────────────────────┤
│ 4. SESSİZ ÖLÜM NÖBETİ (Dead Man's Snitch / Cadence)         │
│    Her gün çalışması gereken iş sinyal vermediyse alarm!    │
├─────────────────────────────────────────────────────────────┤
│ 5. DOĞRUDAN BİLDİRİM (HTTPS Gmail REST API)                 │
│    Port engeline takılmadan doğrudan gelen kutunuza alarm.  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Hızlı Kullanım

### 1. Konsoldan Tek Seferlik Denetim Koşmak:
```bash
cd Projeler/Merkezi_Sentinel
python runner.py
```

### 2. Denetim Yapıp Hata Varsa Doğrudan E-Posta İletmek:
```bash
python runner.py --alert
```

### 3. Canlı Görsel Web Dashboard'unu Açmak:
```bash
python dashboard/dashboard_server.py
```
👉 Tarayıcınızda açın: `http://localhost:8787`
*(Cam efektli arayüz, KPI sayaçları, tüm projelerin canlı durumları ve tek-tık "⚡ Şimdi Tara" butonu).*

---

## 🔌 Yeni ve Mevcut Projeler İçin Kalp Atışı (Heartbeat) SDK'sı

Herhangi bir projede (mevcut veya yeni) sadece 1 satır ekleyerek Sentinel ile konuşabilirsiniz:

```python
from heartbeat import ping, report_deliverable, report_error

# Görev başlangıcında veya periyodik:
ping("Proje_Adi", status="running", message="İşlem başladı")

# Çıktı tamamlandığında:
report_deliverable("Proje_Adi", "video_render", "ID_12345")

# Hata yakalandığında:
report_error("Proje_Adi", "Beklenmeyen API hatası")
```
> **Önemli Not:** Bu SDK'yı çağırmayı unutsanız bile Sentinel'in **dış gözlemcileri** (Typefully, Webhook pings, dosya hareketleri) projenizi otomatik olarak korumaya devam eder.

---

## ☁️ Railway Üzerinde 7/24 Otomatik Çalıştırma

Proje kökünde hazır bulunan `railway.json` sayesinde Railway'e deploy edildiğinde:
* Her saat başı (`0 * * * *`) tüm filoyu tarar.
* Bir aksama olduğunda 3 saatlik akıllı cooldown (tekrar freni) ile doğrudan e-posta gönderir.
* Sunucunuzdaki veya diğer botlarınızdaki tüm kesintilerden anında haberiniz olur.
