<!-- PR'ı açmadan önce lütfen tüm checkboxları doldur. Doldurulmayan
     bölümler review'ı yavaşlatır. Title için Conventional Commits:
     feat: / fix: / refactor: / docs: / build: / chore: / test: -->

## Özet

<!-- 1-2 cümle: ne değiştirdin ve neden? -->

## İlgili issue / discussion

<!-- Closes #N, Refs #M -->

## Değişiklik tipi

- [ ] 🐛 Bug fix (geriye uyumlu)
- [ ] ✨ Yeni feature (geriye uyumlu)
- [ ] 💥 Breaking change (mevcut davranışı kırar)
- [ ] 📝 Documentation
- [ ] 🧪 Test
- [ ] 🔧 Refactor / iç değişiklik (kullanıcı görmez)
- [ ] 🔒 Security
- [ ] 🌍 i18n (çeviri / dil destek)

## Test / doğrulama

<!-- Manuel test adımları, ekran görüntüsü, log çıktısı. -->

- [ ] `pytest -q` lokal'de geçti
- [ ] Yeni feature için test yazıldı (varsa)
- [ ] GUI değişikliği varsa: ekran görüntüsü ekledim
- [ ] CLI değişikliği varsa: `--help` çıktısı güncellendi

## Kullanıcı görünür değişiklik?

- [ ] Hayır (sadece iç refactor / test / docs)
- [ ] Evet — CHANGELOG'a `[Unreleased]` altında entry ekledim
- [ ] Evet — yeni string `_()` ile sarıldı, `po/messages.pot` regenerate edildi (`cd po && make pot`)

## Güvenlik / yıkıcı işlem etkisi

- [ ] Yok
- [ ] Var — yıkıcı bir code path eklendi/değişti. `SECURITY.md`'deki
      invariant'ları kontrol ettim:
      - [ ] Control API'den tetiklenemez
      - [ ] Trash mode default'u korunur
      - [ ] Active-project / user-data exclusion uygulanır
      - [ ] `subprocess` argümanları list formunda (`shell=True` yok veya gerekçeli)

## Notlar

<!-- Reviewer için bilmesi gerekenler: known limitations veya bağlam. -->
