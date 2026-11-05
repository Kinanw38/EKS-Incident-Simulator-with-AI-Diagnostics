# מה שונה בפרויקט ולמה (שלב 1)

המסמך הזה נועד לעזור להסביר כל שינוי בראיון. לכל שינוי: מה שונה, איזו בעיה זה פותר, איך להסביר בשתי משפטים, ומה הייתי עושה אחרת בפרודקשן.

הציון של DevOps Repo Checker לפני השינויים: 68/100. הציון אחרי: _(למלא אחרי הרצה חוזרת של הכלי)_.

---

## 1. הקונטיינר לא רץ יותר כ-root

- **מה שונה:** ב-`backend/Dockerfile` נוצר משתמש מערכת `app`, הקבצים שלו, ו-`USER app`. הבסיס נשאר `python:3.11-slim`.
- **למה:** אם מישהו מנצל פרצה באפליקציה, הוא מקבל הרשאות של המשתמש שהאפליקציה רצה בו. root בתוך קונטיינר נותן לו הרבה יותר מדי.
- **בראיון:** "קונטיינר שרץ כ-root הופך כל פרצה באפליקציה לפרצה חמורה יותר, לכן הרצתי אותו כמשתמש ללא הרשאות. ה-CI גם בודק את זה בכל build."
- **בפרודקשן:** גם `readOnlyRootFilesystem`, `runAsNonRoot` ו-`securityContext` ב-Kubernetes, ותמונת בסיס מינימלית (distroless).

## 2. HEALTHCHECK ו-.dockerignore

- **מה שונה:** `HEALTHCHECK` שפונה ל-`/api/health` עם `curl` (שכבר הותקן "לבדיקות בריאות" אבל לא היה בשימוש). הוספתי `backend/.dockerignore`.
- **למה:** Docker יודע להבדיל בין קונטיינר שרץ לקונטיינר שבאמת עובד. `.dockerignore` מונע מ-`.venv` ומקבצי בדיקות להיכנס לתמונה.
- **בראיון:** "קונטיינר יכול להיות 'רץ' ובפועל תקוע. ה-healthcheck נותן לפלטפורמה דרך לדעת."
- **בפרודקשן:** ב-Kubernetes משתמשים ב-liveness ו-readiness probes במקום HEALTHCHECK של Docker.

## 3. בדיקות אוטומטיות (pytest)

- **מה שונה:** תיקיית `backend/tests` עם 57 בדיקות: ה-allowlist של הטרמינל (כולל ניסיונות הזרקה כמו `;`, `&&`, `$()`), תקינות התרחישים וקבצי ה-YAML שלהם, ה-fallback של ה-RCA, כל ה-API במצב Demo, וקוד ה-live עם לקוח Kubernetes מדומה.
- **למה:** בלי בדיקות, כל שינוי יכול לשבור משהו בלי שאף אחד יידע. במיוחד חשוב לבדוק את האבטחה של הטרמינל.
- **בראיון:** "בדקתי את ה-allowlist מול רשימה של פקודות מסוכנות, והבדיקות רצות ב-CI בכל push. כך שינוי עתידי שיפתח חור יישבר מיד."
- **בפרודקשן:** בדיקות אינטגרציה מול קלאסטר זמני (kind), ומדידת כיסוי קוד.

## 4. CI: הרשאות מינימליות, concurrency, שלושה jobs חדשים

- **מה שונה:** `permissions: contents: read` ברמת ה-workflow, `concurrency` (ריצה חדשה מבטלת ישנה), job של בדיקות, job של build לפרונט, ובדיקה שהקונטיינר לא root. ה-job של Docker תלוי בכולם.
- **למה:** ברירת המחדל של `GITHUB_TOKEN` רחבה מדי. הרשאות מינימליות מצמצמות נזק אם action נפרץ.
- **בראיון:** "עקרון ההרשאה המינימלית חל גם על ה-pipeline."
- **בפרודקשן:** pinning של actions ל-commit SHA, ו-environments עם approvals לפריסה.

## 5. אבטחה אוטומטית: CodeQL ו-Dependabot

- **מה שונה:** `.github/workflows/codeql.yml` (Python ו-JavaScript, בכל push ופעם בשבוע) ו-`.github/dependabot.yml` (pip, npm, docker, terraform, github-actions).
- **למה:** שתי הבדיקות מובנות ב-GitHub, בלי חשבון ובלי מפתח. CodeQL מחפש פרצות בקוד, Dependabot מעדכן תלויות עם חולשות.
- **החלטה:** בהתחלה תכננתי Trivy, אבל בחרתי ב-CodeQL כי הוא של GitHub עצמה, ולא רציתי להוסיף action של צד שלישי.
- **בפרודקשן:** גם סריקת תמונות (Trivy או Grype) וסריקת Terraform (tfsec או Checkov).

## 6. קובץ `.terraform.lock.hcl` כבר לא ב-.gitignore

- **מה שונה:** הסרתי אותו מ-`.gitignore`. **צריך לעשות לו commit** אחרי ה-`terraform init` הראשון (ראה למטה).
- **למה:** הקובץ נועל את גרסאות ה-providers, כך שכל ריצה (גם ב-CI) משתמשת באותן גרסאות.
- **בראיון:** "זה כמו package-lock.json, רק ל-Terraform."

## 7. endpoint של EKS מוגבל ל-IP שלי

- **מה שונה:** משתנה `public_access_cidrs` ב-Terraform (ברירת מחדל פתוחה, עם ולידציה), ו-`setup.sh` מזהה את ה-IP הציבורי שלי (`checkip.amazonaws.com`) ומעביר אותו. אפשר לעקוף עם `EKS_ALLOWED_CIDR`. אם הזיהוי נכשל, הסקריפט נעצר ולא משאיר את ה-endpoint פתוח.
- **למה:** ה-API של Kubernetes היה פתוח לכל האינטרנט. גם עם אימות, זה שטח תקיפה מיותר.
- **בראיון:** "השארתי את ה-endpoint ציבורי כי אני מריץ מהמחשב שלי, אבל הגבלתי אותו ל-IP שלי. בפרודקשן הייתי משתמש ב-endpoint פרטי עם VPN או bastion."
- **שים לב:** אם ה-IP שלך משתנה (נתב, hotspot), `kubectl` יפסיק לעבוד. ריצה חוזרת של `setup.sh` מעדכנת את זה.

## 8. Terraform state נשאר מקומי (החלטה מכוונת)

- **מה שונה:** שום קוד. הוספתי ל-README סעיף "Design Decisions".
- **למה:** בסימולטור חד-משתמשי וקצר-טווח, backend מרוחק (S3 וטבלת נעילה) מוסיף משאבים שעלולים לשרוד את ה-destroy.
- **בראיון:** "ה-Checker סימן את זה והחלטתי לא לתקן. ידעתי מה הפתרון בפרודקשן (S3 עם נעילה), אבל כאן זה רק מוסיף משאבים לנקות."

## 9. באגים שמצאתי בסקירה

1. **`kubectl version --short`:** הדגל הוסר מ-kubectl (1.28+). ה-allowlist עודכן ל-`kubectl version` ול-`kubectl version --client`, ויש בדיקה.
2. **תרחיש `broken_routing` במצב live:** הטלמטריה חיפשה פודים עם `app=payment-service`, אבל התווית האמיתית היא `payment-processor`. נוסף שדה `pod_label` לכל תרחיש, ולתרחיש הניתוב נוסף גם מידע על endpoints של ה-Service (דרך EndpointSlice, כי `Endpoints` מיושן). ה-fallback הסטטי הסתיר את הבאג, ולכן יש לו בדיקת רגרסיה.
3. **תרחיש `crashloop`:** Secret חסר ב-`secretKeyRef` משאיר את הפוד ב-`CreateContainerConfigError`, לא ב-`CrashLoopBackOff` (הקונטיינר בכלל לא נוצר). תיקנתי טקסטים, פלט הדמו וה-README. ה-id נשאר `crashloop` כדי לא לשבור את ה-API.
4. **`/api/remediate`:** שלבי "Verifying readiness: COMPLETED" היו קבועים בקוד. עכשיו במצב live מתבצעת בדיקה אמיתית של ה-Deployment (עד 60 שניות). אם הוא לא מוכן, התשובה היא `APPLIED_NOT_READY` והפרונט לא מכריז "Resolved". במצב Demo השלבים מסומנים `SIMULATED`.
5. **`rca_engine.py`:** הוחלף `except: pass` בלוגים, וה-timeout הוא `(2, 30)` שניות וניתן לשינוי עם `OLLAMA_TIMEOUT`. מודל מקומי צריך יותר משלוש שניות.
6. **`requirements.txt`:** הגרסאות ננעלו (`==`) ונוסף PyYAML במפורש, כי הקוד מייבא אותו ישירות והוא היה תלות עקיפה.

- **בראיון על 9.2 ו-9.4:** "מצאתי שה-fallback הדטרמיניסטי מסתיר באגים של מצב live, כי הוא מחזיר תשובה נכונה לפי ה-id בלי קשר לטלמטריה. הוספתי בדיקות שמוודאות שהטלמטריה באמת מחפשת את התווית הנכונה."

---

## מה צריך לבדוק על קלאסטר אמיתי (לא נבדק עדיין)

- `kubectl get pods` בתרחיש `crashloop`: האם הסטטוס באמת `CreateContainerConfigError`.
- הרצת תרחיש ותיקון: האם `/api/remediate` מחזיר `RESOLVED` אחרי שהפוד מוכן.
- `setup.sh` מזהה IP, וה-endpoint של EKS נגיש רק ממנו.
- אחרי ה-`terraform init` הראשון: לעשות commit ל-`terraform/.terraform.lock.hcl`.

---

# Stage 2

## 10. נרמול סיומות שורה (`.gitattributes`)

- **מה שונה:** נוסף `.gitattributes` (`* text=auto eol=lf`) וכל הקבצים נורמלו ל-LF ב-commit נפרד.
- **למה:** קבצים עם CRLF ו-LF מעורבים שברו את `terraform fmt` ב-CI. עכשיו ה-diffs נקיים.
- **בראיון:** "קבצים מעורבים גרמו לכשל ב-CI, אז קבעתי LF בכל הריפו עם `.gitattributes`."

## 11. שדרוג `vite` ל-8 (מייג'ור)

- **מה שונה:** `vite` עלה מ-7 ל-8.3.x (`npm install -D vite@^8.3.5`). `npm run build` עובר.
- **למה:** Dependabot הציע את זה כמייג'ור. במקום להתעלם ממייג'ורים, שדרגתי בצורה מבוקרת, תלות אחת בכל commit.
- **שים לב:** vite 8 דורש Node ‏`^20.19` או `>=22.12`. ב-CI מוגדר Node 22 ולכן זה בסדר.
- **בראיון:** "שדרגתי מייג'ור אחד בכל פעם, ואחרי כל שדרוג הרצתי build לפני commit."
- **בפרודקשן:** הייתי בודק גם את ה-preview ואת ה-dev server, לא רק build.

## 12. שדרוג `@vitejs/plugin-react` ל-6 (מייג'ור)

- **מה שונה:** ‏`@vitejs/plugin-react` עלה מ-4 ל-6.2.x. הגרסה הזאת דורשת vite 8, ולכן היא באה אחרי סעיף 11. `npm run build` עובר בלי שינוי בקוד או ב-`vite.config.js`.
- **למה:** התלות הזאת נכשלה ב-Dependabot כשהוצעה לבד, כי היא תלויה בגרסת vite.
- **בראיון:** "שמתי לב לתלות בין החבילות: plugin-react 6 דורש vite 8, אז שדרגתי קודם את vite."
- **בפרודקשן:** הייתי מוסיף בדיקות frontend, כדי שבנייה תקינה לא תהיה הבדיקה היחידה.

## 13. שדרוג `tailwindcss` ל-4 (מייג'ור)

- **מה שונה:** הרצתי את הכלי הרשמי `npx @tailwindcss/upgrade` לפי מדריך ההגירה של Tailwind. הכלי:
  - מחק את `tailwind.config.js` והעביר את צבעי ה-`brand` והפונט ל-`@theme` בתוך `src/index.css`;
  - החליף `@tailwind base/components/utilities` ב-`@import 'tailwindcss'`;
  - עדכן את `postcss.config.js` לפלאגין `@tailwindcss/postcss` והסיר את `autoprefixer` (v4 כולל אותו);
  - שינה שמות של כמה classes בקבצי JSX;
  - הוסיף בלוק תאימות שמחזיר את צבע ה-border לברירת המחדל של v3, כי ב-v4 ברירת המחדל היא `currentcolor`.
- **למה זה היה בטוח יחסית:** הקונפיג קטן, אין `@apply` ואין פלאגינים. `npm run build` עובר.
- **לא נבדק:** המראה בדפדפן. build ירוק לא מבטיח שהעיצוב נראה זהה. צריך לפתוח את האתר (`npm run dev`) ולעבור על כל המסכים.
- **בראיון:** "השתמשתי בכלי ההגירה הרשמי, קראתי את ה-diff, ובדקתי שאין פלאגינים או `@apply` שעלולים להישבר."
- **בפרודקשן:** הייתי מוסיף בדיקות ויזואליות (screenshots) כדי לתפוס שינויי עיצוב אוטומטית.

## 14. מספר גרסה: v2.0.0

- **מה שונה:** הגרסה עלתה מ-1.0.0 ל-2.0.0 במקום אחד בתצוגה (`App.jsx`, פינה שמאלית עליונה) ובשלושה מקומות בקוד: `backend/app/main.py`, `frontend/package.json` ו-`package-lock.json`.
- **למה:** זו גרסה חדשה של הפרויקט (Stage 2 והשדרוגים). מספר מייג'ור עולה כי השתנו ספריות ליבה (vite, tailwind).
- **נבדק:** ‏`pytest` (57 עברו) ו-`npm run build`. ה-API לא השתנה.
- **בראיון:** "בניתי לפי semantic versioning: מייג'ור עולה כשיש שינוי גדול."

## 15. הגבלת Dependabot

- **מה שונה:** `open-pull-requests-limit: 3` לכל מערכת, וקיבוץ של עדכוני minor/patch ל-PR אחד (בכל המערכות חוץ מ-docker, ששם אין מה לקבץ).
- **למה:** בגלל 11 PRs בבת אחת לא היה אפשר לדעת מה חשוב. עדכוני מייג'ור **לא** מושתקים: כל אחד מגיע כ-PR נפרד כדי שאשדרג אותו בצורה מתוכננת (מדריך הגירה, build, ואז merge).
- **בראיון:** "הגבלתי רעש אבל לא התעלמתי ממייג'ורים. התעלמות היא חוב טכני שמצטבר."

## 16. Terraform: גרסת Kubernetes, AMI, log group, ולידציה

- **`kubernetes_version`:** משתנה חדש עם ברירת מחדל `1.35`. בדקתי עם `aws eks describe-cluster-versions`: ‏1.35 ב-standard support עד 27.3.2027, ו-1.34 מסתיים ב-2.12.2026. 1.33 ומטה כבר ב-extended support, שעולה $0.60 לשעה לעומת $0.10. קיימות גם 1.36 ו-1.37, אבל בחרתי 1.35 לפי ההחלטה שלנו. פלט חדש: `cluster_version`.
- **`ami_type = "AL2023_x86_64_STANDARD"`** מפורש בקבוצת הצמתים, כי AL2 כבר לא מתפרסם.
- **log group ב-Terraform** (`/aws/eks/<cluster>/cluster`, שמירה 7 ימים), והקלאסטר תלוי בו. עד עכשיו EKS יצר אותו לבד, והוא נשאר אחרי `destroy` ועלה כסף.
- **ולידציה:** `min <= desired <= max`. ולידציה שמפנה למשתנים אחרים דורשת Terraform 1.9 ומעלה, ולכן העליתי את `required_version` ל-`>= 1.9.0` (ב-CI כבר 1.9.8).
- **`.terraform.lock.hcl`** נכנס ל-git: נעילת גרסאות providers. כך כולם משתמשים באותן גרסאות.
- **בראיון:** "בעיה שחוזרת היא משאבים שנוצרים מחוץ ל-Terraform ונשארים אחרי destroy. הגדרתי אותם בקוד, כדי ש-Terraform יהיה הבעלים שלהם."
- **לא נבדק על AWS:** לא הרצתי apply. רק `fmt` ו-`validate`.

## 17. `setup.sh` ו-`vite.config.js`: בטיחות ובהירות

- **בדיקות לפני ההרצה:** ‏`aws sts get-caller-identity` מדפיס את החשבון והאזור ומבקש אישור; בדיקת Terraform 1.9 ומעלה; הערכת עלות. דילוג על השאלות עם `--yes`.
- **האזנה רק ל-`127.0.0.1`:** הבקאנד ו-Vite (גם ב-`vite.config.js`, שהיה `host: true`). הבקאנד ב-live בלי הזדהות ויכול להריץ kubectl על הקלאסטר שלך, ולכן אסור שיהיה נגיש מהרשת.
- **Process group לכל שירות** (`setsid`) ושמירת ה-PGID. כך `destroy.sh` יכול להרוג את כל העץ, כולל תהליך node יתום ש-`npm run dev` משאיר.
- **`kubectl wait --for=condition=Ready nodes --all --timeout=300s`** במקום לולאת `kubectl get nodes`.
- **ייבוא ה-log group:** אם קבוצת הלוגים קיימת ב-AWS ואינה ב-state של Terraform (שארית מהרצות קודמות), `setup.sh` מבצע `terraform import` במקום להיכשל ב-"already exists".
- **הודעת שגיאה לפי שלב:** מציינת באיזה שלב נכשל, ואם זה היה `terraform apply`, מפנה להרצת `./scripts/destroy.sh`.
- **פלט קריא:** כותרת "Step N/8" לכל שלב, עם הסבר קצר מה קורה ולמה.
- **גם:** fallback ל-`shasum -a 256`, והודעה ברורה אם פורט תפוס.
- **בראיון:** "הסקריפט שואל לפני שהוא יוצר משאבים שעולים כסף, מאזין רק ל-localhost כי אין לו הזדהות, ומנהל תהליכים בקבוצות כדי לא להשאיר יתומים."
- **לא נבדק על AWS אמיתי:** זיהוי ה-IP, ה-import של ה-log group, והאזנה ל-127.0.0.1. הריצו וודאו.

## 18. label אחיד על כל משאבי הסימולטור

- **מה שונה:** כל manifest (ב-`scenarios.py` ובקבצי `k8s/*.yaml`, כולל ה-Secret של תיקון `crashloop`) קיבל `app.kubernetes.io/part-of: incident-simulator`.
- **למה:** `destroy.sh` ימחק רק משאבים עם ה-label הזה. קודם הוא מחק `--all --all-namespaces`, כולל `kube-system`.
- **בראיון:** "השתמשתי ב-label הסטנדרטי של Kubernetes כדי שהניקוי יהיה מדויק ולא יגע במה שלא שלי."

## 19. `destroy.sh`: בטוח, מדויק, ועם בדיקת PASS/FAIL

- **בטיחות:** הסקריפט לא סומך על ה-context הנוכחי של kubectl. הוא קורא את שם הקלאסטר והאזור מ-Terraform, יוצר kubeconfig זמני (`aws eks update-kubeconfig --kubeconfig <tmp>`) ומעביר אותו ל-kubectl במפורש. אם הקלאסטר לא נגיש (למשל ה-IP שלך השתנה), הוא מדלג על ניקוי Kubernetes ולא נוגע בשום דבר אחר.
- **היקף:** מוחק רק משאבים עם `app.kubernetes.io/part-of=incident-simulator` (סעיף 18), ולא `--all --all-namespaces` כולל `kube-system` כמו קודם. כל Service מסוג `LoadBalancer` נמחק, כי load balancer ב-AWS חוסם מחיקת VPC.
- **המתנה חכמה:** במקום `sleep 45` עיוור, ממתין רק אם היו LoadBalancers, בבדיקה כל 10 שניות עד 3 דקות.
- **`terraform destroy`:** עד 3 ניסיונות, 60 שניות בין ניסיון לניסיון (שגיאת `DependencyViolation` ב-VPC היא לרוב זמנית). בכישלון סופי מודפסים אבחונים של network interfaces ושל security groups.
- **בדיקה אחרי destroy:** רשימת PASS/FAIL: אין משאבים עם התג `Project=AI-Incident-Simulator`, הקלאסטר נעלם, NAT gateways נמחקו, Elastic IP שוחרר, ה-log group נמחק.
- **ניקוי `~/.kube/config`:** נמחקים רק ה-context, ה-cluster וה-user של הקלאסטר הזה.
- **עצירת שירותים מקומיים:** קודם process group, ואז בדיקה שהפורטים פנויים. `.venv` ו-`node_modules` אף פעם לא נמחקים.
- **`--yes`/`-y`:** ללא שאלת אישור. ברירת המחדל נשארת אינטראקטיבית.
- **פלט:** "Step N/7" עם הסבר קצר לכל שלב, ו-`shellcheck` נקי על שני הסקריפטים.
- **בראיון:** "הקשחתי את ה-destroy לפי הסיפור 'לא להשאיר כלום ולא להיתקע': מוחק רק מה שלי, מנסה שוב על שגיאות זמניות, ובסוף בודק מול AWS שבאמת לא נשאר כלום."
- **לא נבדק על AWS אמיתי:** כל הסקריפט. הריצו `destroy.sh` על קלאסטר אמיתי וודאו שרשימת ה-PASS/FAIL נכונה.

## 20. תיקון בדיקת ה-rollout ב-`/api/remediate`

- **הבעיה (מצאתי בסקירת Stage 1):** הבדיקה `ready_replicas >= desired` יכולה להחזיר "מוכן" באמצע rollout, כי ה-pod הישן עדיין Ready ועד שה-pod החדש עולה הוא מספיק כדי להצליח.
- **התיקון:** עכשיו נדרש גם `updated_replicas >= desired` וגם שלא נשארו pods ישנים (`replicas <= desired`). זה אותו רעיון כמו `kubectl rollout status`. נוסף טסט שמדמה pod ישן שרץ.
- **בראיון:** "בדיקת readiness שבודקת רק כמה pods Ready מפספסת rollout באמצע. צריך לבדוק גם שהם מהגרסה החדשה."
- **לא נבדק על קלאסטר אמיתי.** נבדק רק עם טסטים עם mocks.
