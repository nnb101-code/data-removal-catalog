# Data Removal — source catalog · קטלוג מקורות

**English** · [עברית](#עברית)

The list of people-search sites and data brokers, and the law profiles, used by the Data Removal Android app. It holds no personal data. The app downloads `catalog.json` and `catalog.json.sig` from this public repository, checks the ECDSA P-256 signature against a public key built into the app, and keeps the last good copy. A forged or broken file is ignored.

| File | What it is |
| --- | --- |
| `sources/curated.json` | Priority sites prepared by hand: channel, opt-out URL, fields each site needs, verification, notes |
| `sources/laws.json` | Law profiles (New Jersey, Generic) with request, follow-up and complaint templates |
| `tools/build_catalog.py` | Builds `catalog.json` from the two files above plus the Optery directory and DuckDuckGo's broker definitions |
| `tools/sign_catalog.py` | Signs `catalog.json` with the `CATALOG_SIGNING_KEY` secret |
| `.github/workflows/publish.yml` | Rebuilds and signs on every change and weekly |

Confidence levels: `tested` (flow checked against the live site, with date) · `untested` (prepared by hand, not yet checked live) · `listed` (imported, nothing is sent automatically) · `defunct`.

**Licence.** Built on the [Optery Data Brokers Directory](https://github.com/optery/optery-data-brokers-directory) and [BADBOOL](https://github.com/yaelwrites/Big-Ass-Data-Broker-Opt-Out-List), both CC BY-NC-SA. This catalog is shared under the same licence, for non-commercial use. Search addresses, opt-out pages and form fields also come from [DuckDuckGo's Personal Information Removal broker definitions](https://github.com/duckduckgo/Android/tree/develop/pir/pir-impl/src/main/assets/brokers) (Apache License 2.0), adapted.

---

## עברית

רשימת אתרי חיפוש האנשים וברוקרי המידע, ופרופילי החוק, שאפליקציית הסרת המידע משתמשת בהם. אין בה שום מידע אישי. האפליקציה מורידה מהמאגר הציבורי הזה את `catalog.json` ו־`catalog.json.sig`, בודקת חתימת ECDSA P-256 מול מפתח ציבורי שמובנה באפליקציה, ושומרת את העותק התקין האחרון. קובץ מזויף או פגום נדחה.

| קובץ | מה הוא |
| --- | --- |
| `sources/curated.json` | אתרים בעדיפות שהוכנו ידנית: ערוץ, קישור הסרה, השדות שכל אתר צריך, אימות, הערות |
| `sources/laws.json` | פרופילי חוק (ניו ג'רזי, כללי) עם תבניות בקשה, תזכורת ותלונה |
| `tools/build_catalog.py` | בונה את `catalog.json` משני הקבצים למעלה מהמאגר של Optery ומהגדרות הברוקרים של DuckDuckGo |
| `tools/sign_catalog.py` | חותם על `catalog.json` עם הסוד `CATALOG_SIGNING_KEY` |
| `.github/workflows/publish.yml` | בונה וחותם מחדש בכל שינוי ופעם בשבוע |

רמות ביטחון: `tested` (התהליך נבדק מול האתר החי, עם תאריך) · `untested` (הוכן ידנית, עוד לא נבדק חי) · `listed` (יובא, שום דבר לא נשלח אוטומטית) · `defunct` (לא פעיל).

**רישיון.** מבוסס על [המאגר של Optery](https://github.com/optery/optery-data-brokers-directory) ועל [BADBOOL](https://github.com/yaelwrites/Big-Ass-Data-Broker-Opt-Out-List), שניהם CC BY-NC-SA. הקטלוג משותף באותו רישיון, לשימוש לא מסחרי. כתובות חיפוש, דפי הסרה ושדות טפסים מגיעים גם מ[הגדרות הברוקרים של DuckDuckGo](https://github.com/duckduckgo/Android/tree/develop/pir/pir-impl/src/main/assets/brokers) (רישיון Apache 2.0), בעיבוד.
