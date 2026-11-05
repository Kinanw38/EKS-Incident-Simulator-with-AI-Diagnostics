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
