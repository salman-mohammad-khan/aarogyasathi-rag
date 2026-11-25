# S2 retrieval bake-off: golden_retrieval_hard.yaml

30 questions (en 8, hi 8, hinglish 14). hit@5 / MRR@10.

| Method | Query | English | Hindi | Hinglish | All |
|---|---|---|---|---|---|
| bm25 | as typed | 0.88 / 0.72 | 0.00 / 0.00 | 0.21 / 0.13 | 0.33 / 0.25 |
| bm25 | rewrite gemma-3-27b | 0.88 / 0.72 | 0.88 / 0.62 | 0.93 / 0.73 | 0.90 / 0.70 |
| bm25 | rewrite gpt-oss-120b | 0.88 / 0.72 | 0.88 / 0.63 | 0.71 / 0.61 | 0.80 / 0.65 |
| bm25 | rewrite gemma-3-27b+glossary | 0.88 / 0.72 | 0.75 / 0.69 | 0.93 / 0.80 | 0.87 / 0.75 |
| bm25 | rewrite gpt-oss-120b+glossary | 0.88 / 0.72 | 0.75 / 0.58 | 0.71 / 0.60 | 0.77 / 0.63 |
| e5-base | as typed | 0.75 / 0.64 | 0.50 / 0.39 | 0.21 / 0.21 | 0.43 / 0.38 |
| e5-base+bm25 | as typed | 1.00 / 0.76 | 0.50 / 0.19 | 0.21 / 0.19 | 0.50 / 0.34 |
| e5-base | rewrite gemma-3-27b | 0.75 / 0.64 | 0.88 / 0.81 | 0.93 / 0.84 | 0.87 / 0.78 |
| e5-base+bm25 | rewrite gemma-3-27b | 1.00 / 0.76 | 0.88 / 0.81 | 0.93 / 0.78 | 0.93 / 0.79 |
| e5-base | rewrite gpt-oss-120b | 0.75 / 0.64 | 0.75 / 0.72 | 0.64 / 0.66 | 0.70 / 0.67 |
| e5-base+bm25 | rewrite gpt-oss-120b | 1.00 / 0.76 | 0.88 / 0.78 | 0.79 / 0.65 | 0.87 / 0.71 |
| e5-base | rewrite gemma-3-27b+glossary | 0.75 / 0.64 | 0.88 / 0.73 | 0.93 / 0.89 | 0.87 / 0.78 |
| e5-base+bm25 | rewrite gemma-3-27b+glossary | 1.00 / 0.76 | 0.75 / 0.77 | 1.00 / 0.93 | 0.93 / 0.84 |
| e5-base | rewrite gpt-oss-120b+glossary | 0.75 / 0.64 | 0.88 / 0.81 | 0.86 / 0.70 | 0.83 / 0.72 |
| e5-base+bm25 | rewrite gpt-oss-120b+glossary | 1.00 / 0.76 | 0.88 / 0.70 | 0.93 / 0.76 | 0.93 / 0.75 |
| labse | as typed | 0.50 / 0.25 | 0.62 / 0.34 | 0.29 / 0.11 | 0.43 / 0.21 |
| labse+bm25 | as typed | 1.00 / 0.81 | 0.50 / 0.17 | 0.29 / 0.18 | 0.53 / 0.35 |
| labse | rewrite gemma-3-27b | 0.50 / 0.25 | 0.75 / 0.51 | 0.79 / 0.49 | 0.70 / 0.43 |
| labse+bm25 | rewrite gemma-3-27b | 1.00 / 0.81 | 0.75 / 0.50 | 0.86 / 0.67 | 0.87 / 0.66 |
| labse | rewrite gpt-oss-120b | 0.50 / 0.25 | 0.50 / 0.35 | 0.71 / 0.53 | 0.60 / 0.41 |
| labse+bm25 | rewrite gpt-oss-120b | 1.00 / 0.81 | 0.62 / 0.47 | 0.71 / 0.58 | 0.77 / 0.61 |
| labse | rewrite gemma-3-27b+glossary | 0.50 / 0.25 | 0.62 / 0.41 | 0.79 / 0.52 | 0.67 / 0.42 |
| labse+bm25 | rewrite gemma-3-27b+glossary | 1.00 / 0.81 | 0.75 / 0.60 | 0.79 / 0.71 | 0.83 / 0.71 |
| labse | rewrite gpt-oss-120b+glossary | 0.50 / 0.25 | 0.62 / 0.42 | 0.86 / 0.56 | 0.70 / 0.44 |
| labse+bm25 | rewrite gpt-oss-120b+glossary | 1.00 / 0.81 | 0.75 / 0.67 | 0.79 / 0.68 | 0.83 / 0.71 |
| titan-v2 | as typed | 1.00 / 0.85 | 0.50 / 0.32 | 0.36 / 0.19 | 0.57 / 0.40 |
| titan-v2+bm25 | as typed | 1.00 / 0.81 | 0.38 / 0.21 | 0.21 / 0.15 | 0.47 / 0.34 |
| titan-v2 | rewrite gemma-3-27b | 1.00 / 0.85 | 1.00 / 0.82 | 0.79 / 0.70 | 0.90 / 0.77 |
| titan-v2+bm25 | rewrite gemma-3-27b | 1.00 / 0.81 | 0.88 / 0.73 | 0.93 / 0.74 | 0.93 / 0.76 |
| titan-v2 | rewrite gpt-oss-120b | 1.00 / 0.85 | 0.88 / 0.57 | 0.64 / 0.49 | 0.80 / 0.61 |
| titan-v2+bm25 | rewrite gpt-oss-120b | 1.00 / 0.81 | 0.75 / 0.71 | 0.79 / 0.65 | 0.83 / 0.71 |
| titan-v2 | rewrite gemma-3-27b+glossary | 1.00 / 0.85 | 0.88 / 0.65 | 0.79 / 0.67 | 0.87 / 0.71 |
| titan-v2+bm25 | rewrite gemma-3-27b+glossary | 1.00 / 0.81 | 0.88 / 0.71 | 1.00 / 0.74 | 0.97 / 0.75 |
| titan-v2 | rewrite gpt-oss-120b+glossary | 1.00 / 0.85 | 1.00 / 0.60 | 0.71 / 0.66 | 0.87 / 0.69 |
| titan-v2+bm25 | rewrite gpt-oss-120b+glossary | 1.00 / 0.81 | 0.75 / 0.70 | 0.86 / 0.74 | 0.87 / 0.75 |

## Questions missed (no correct chunk in the top 5)

- **e5-base | as typed**: child-loose-motion-cramps (hinglish), yellow-eyes-urine (hinglish), dizzy-headache-after-sun (hi), newborn-not-feeding (hinglish), fever-test-malaria-dengue (hinglish), snakebite-unsure-marks (hinglish), pregnancy-swelling-headache (hinglish), vaccines-six-weeks (hi), fever-after-vaccine (hinglish), tb-home-precautions (en), hunger-thirst-weight-loss (hinglish), krait-night-bite (en), feeding-during-diarrhoea (hinglish), malaria-full-course (hi), blood-in-sputum (hi), haemoglobin-normal (hinglish), observe-dog-ten-days (hinglish)
- **e5-base+bm25 | as typed**: child-loose-motion-cramps (hinglish), yellow-eyes-urine (hinglish), dizzy-headache-after-sun (hi), newborn-not-feeding (hinglish), fever-test-malaria-dengue (hinglish), snakebite-unsure-marks (hinglish), pregnancy-swelling-headache (hinglish), vaccines-six-weeks (hi), fever-after-vaccine (hinglish), hunger-thirst-weight-loss (hinglish), feeding-during-diarrhoea (hinglish), malaria-full-course (hi), blood-in-sputum (hi), haemoglobin-normal (hinglish), observe-dog-ten-days (hinglish)
- **e5-base | rewrite gemma-3-27b**: vaccines-six-weeks (hi), tb-home-precautions (en), hunger-thirst-weight-loss (hinglish), krait-night-bite (en)
- **e5-base+bm25 | rewrite gemma-3-27b**: yellow-eyes-urine (hinglish), vaccines-six-weeks (hi)
- **e5-base | rewrite gpt-oss-120b**: yellow-eyes-urine (hinglish), snakebite-unsure-marks (hinglish), vaccines-six-weeks (hi), fever-after-vaccine (hinglish), tb-home-precautions (en), hunger-thirst-weight-loss (hinglish), krait-night-bite (en), blood-in-sputum (hi), haemoglobin-normal (hinglish)
- **e5-base+bm25 | rewrite gpt-oss-120b**: yellow-eyes-urine (hinglish), vaccines-six-weeks (hi), fever-after-vaccine (hinglish), hunger-thirst-weight-loss (hinglish)
- **e5-base | rewrite gemma-3-27b+glossary**: vaccines-six-weeks (hi), tb-home-precautions (en), hunger-thirst-weight-loss (hinglish), krait-night-bite (en)
- **e5-base+bm25 | rewrite gemma-3-27b+glossary**: vaccines-six-weeks (hi), malaria-full-course (hi)
- **e5-base | rewrite gpt-oss-120b+glossary**: snakebite-unsure-marks (hinglish), vaccines-six-weeks (hi), tb-home-precautions (en), hunger-thirst-weight-loss (hinglish), krait-night-bite (en)
- **e5-base+bm25 | rewrite gpt-oss-120b+glossary**: yellow-eyes-urine (hinglish), vaccines-six-weeks (hi)
- **labse | as typed**: child-loose-motion-cramps (hinglish), yellow-eyes-urine (hinglish), dizzy-headache-after-sun (hi), newborn-not-feeding (hinglish), fever-test-malaria-dengue (hinglish), snakebite-unsure-marks (hinglish), iron-tablets-pregnancy (en), pregnancy-swelling-headache (hinglish), fever-after-vaccine (hinglish), tb-home-precautions (en), hunger-thirst-weight-loss (hinglish), feeding-during-diarrhoea (hinglish), malaria-full-course (hi), typhoid-vaccine (en), blood-in-sputum (hi), observe-dog-ten-days (hinglish), measles-danger (en)
- **labse+bm25 | as typed**: child-loose-motion-cramps (hinglish), yellow-eyes-urine (hinglish), dizzy-headache-after-sun (hi), newborn-not-feeding (hinglish), fever-test-malaria-dengue (hinglish), snakebite-unsure-marks (hinglish), pregnancy-swelling-headache (hinglish), vaccines-six-weeks (hi), fever-after-vaccine (hinglish), hunger-thirst-weight-loss (hinglish), feeding-during-diarrhoea (hinglish), malaria-full-course (hi), blood-in-sputum (hi), observe-dog-ten-days (hinglish)
- **labse | rewrite gemma-3-27b**: child-loose-motion-cramps (hinglish), snakebite-unsure-marks (hinglish), iron-tablets-pregnancy (en), tb-home-precautions (en), hunger-thirst-weight-loss (hinglish), malaria-full-course (hi), typhoid-vaccine (en), blood-in-sputum (hi), measles-danger (en)
- **labse+bm25 | rewrite gemma-3-27b**: vaccines-six-weeks (hi), hunger-thirst-weight-loss (hinglish), blood-in-sputum (hi), haemoglobin-normal (hinglish)
- **labse | rewrite gpt-oss-120b**: child-loose-motion-cramps (hinglish), dizzy-headache-after-sun (hi), dog-scratch-no-blood (hi), snakebite-unsure-marks (hinglish), iron-tablets-pregnancy (en), pregnancy-swelling-headache (hinglish), tb-home-precautions (en), hunger-thirst-weight-loss (hinglish), malaria-full-course (hi), typhoid-vaccine (en), blood-in-sputum (hi), measles-danger (en)
- **labse+bm25 | rewrite gpt-oss-120b**: child-loose-motion-cramps (hinglish), yellow-eyes-urine (hinglish), dizzy-headache-after-sun (hi), dog-scratch-no-blood (hi), vaccines-six-weeks (hi), hunger-thirst-weight-loss (hinglish), haemoglobin-normal (hinglish)
- **labse | rewrite gemma-3-27b+glossary**: fever-test-malaria-dengue (hinglish), dog-scratch-no-blood (hi), snakebite-unsure-marks (hinglish), iron-tablets-pregnancy (en), tb-home-precautions (en), hunger-thirst-weight-loss (hinglish), malaria-full-course (hi), typhoid-vaccine (en), blood-in-sputum (hi), measles-danger (en)
- **labse+bm25 | rewrite gemma-3-27b+glossary**: child-loose-motion-cramps (hinglish), vaccines-six-weeks (hi), hunger-thirst-weight-loss (hinglish), malaria-full-course (hi), haemoglobin-normal (hinglish)
- **labse | rewrite gpt-oss-120b+glossary**: child-loose-motion-cramps (hinglish), dog-scratch-no-blood (hi), iron-tablets-pregnancy (en), tb-home-precautions (en), hunger-thirst-weight-loss (hinglish), malaria-full-course (hi), typhoid-vaccine (en), blood-in-sputum (hi), measles-danger (en)
- **labse+bm25 | rewrite gpt-oss-120b+glossary**: fever-test-malaria-dengue (hinglish), dog-scratch-no-blood (hi), vaccines-six-weeks (hi), hunger-thirst-weight-loss (hinglish), haemoglobin-normal (hinglish)
- **titan-v2 | as typed**: child-loose-motion-cramps (hinglish), yellow-eyes-urine (hinglish), fever-test-malaria-dengue (hinglish), dog-scratch-no-blood (hi), snakebite-unsure-marks (hinglish), pregnancy-swelling-headache (hinglish), vaccines-six-weeks (hi), fever-after-vaccine (hinglish), hunger-thirst-weight-loss (hinglish), feeding-during-diarrhoea (hinglish), malaria-full-course (hi), blood-in-sputum (hi), observe-dog-ten-days (hinglish)
- **titan-v2+bm25 | as typed**: child-loose-motion-cramps (hinglish), yellow-eyes-urine (hinglish), dizzy-headache-after-sun (hi), fever-test-malaria-dengue (hinglish), dog-scratch-no-blood (hi), snakebite-unsure-marks (hinglish), pregnancy-swelling-headache (hinglish), vaccines-six-weeks (hi), fever-after-vaccine (hinglish), hunger-thirst-weight-loss (hinglish), feeding-during-diarrhoea (hinglish), malaria-full-course (hi), hepb-birth-dose (hinglish), blood-in-sputum (hi), haemoglobin-normal (hinglish), observe-dog-ten-days (hinglish)
- **titan-v2 | rewrite gemma-3-27b**: newborn-not-feeding (hinglish), hunger-thirst-weight-loss (hinglish), observe-dog-ten-days (hinglish)
- **titan-v2+bm25 | rewrite gemma-3-27b**: vaccines-six-weeks (hi), haemoglobin-normal (hinglish)
- **titan-v2 | rewrite gpt-oss-120b**: yellow-eyes-urine (hinglish), dog-scratch-no-blood (hi), snakebite-unsure-marks (hinglish), fever-after-vaccine (hinglish), hunger-thirst-weight-loss (hinglish), observe-dog-ten-days (hinglish)
- **titan-v2+bm25 | rewrite gpt-oss-120b**: yellow-eyes-urine (hinglish), dog-scratch-no-blood (hi), vaccines-six-weeks (hi), hunger-thirst-weight-loss (hinglish), haemoglobin-normal (hinglish)
- **titan-v2 | rewrite gemma-3-27b+glossary**: newborn-not-feeding (hinglish), hunger-thirst-weight-loss (hinglish), blood-in-sputum (hi), observe-dog-ten-days (hinglish)
- **titan-v2+bm25 | rewrite gemma-3-27b+glossary**: vaccines-six-weeks (hi)
- **titan-v2 | rewrite gpt-oss-120b+glossary**: newborn-not-feeding (hinglish), snakebite-unsure-marks (hinglish), hunger-thirst-weight-loss (hinglish), observe-dog-ten-days (hinglish)
- **titan-v2+bm25 | rewrite gpt-oss-120b+glossary**: yellow-eyes-urine (hinglish), fever-test-malaria-dengue (hinglish), dog-scratch-no-blood (hi), vaccines-six-weeks (hi)

## English rewrites used

| Question | gemma-3-27b | gpt-oss-120b | gemma-3-27b+glossary | gpt-oss-120b+glossary |
|---|---|---|---|---|
| pet me marod aur baar baar patla potty ho raha hai bacche ko, kya kare | Is your child experiencing abdominal pain and frequent, loose stools, and what should you do? | Stomach cramp and frequent watery stool in baby—what should be done? | Does the child have abdominal pain and frequent diarrhoea, and what should be done? | Child has abdominal cramps and frequent watery stools, what should I do? |
| aankhein aur peshab peela ho gaya hai, kaunsi bimari hai | Are your eyes and urine yellow, and what disease could this be? | What disease causes aankhein and peshab to become peela? | Is yellowing of the eyes and urine a sign of jaundice? | What disease causes yellow eyes and urine? |
| धूप में काम करने के बाद चक्कर आ रहे हैं और सिर दर्द है, क्या करें? | After working in the sun, experiencing dizziness and headache, what should be done? | After working in the sun I'm dizzy and have a headache—what should I do? | What should I do for dizziness and headache after working in the heat? | I'm dizzy and have a headache after working in the sun; what should I do? |
| naya bachcha doodh nahi pee raha aur bahut sust pada hai | Is the newborn refusing breastmilk or formula and exhibiting lethargy? | Is the newborn not drinking milk and very lethargic? | Is the newborn refusing milk and excessively lethargic? | Is the newborn refusing milk and extremely lethargic? |
| machhar wale bukhar me kaunsi jaanch karani chahiye | Which diagnostic test should be done for dengue fever? | In malaria fever, which test should be done? | What tests should be done for mosquito-borne fever? | Which test should be done for mosquito-borne fever? |
| कुत्ते ने खरोंच मारी है पर खून नहीं निकला, क्या इंजेक्शन लगवाना ज़रूरी है? | Was a rabies injection necessary after the dog scratch, as there was no bleeding? | The dog scratched me but no blood came out; is an injection necessary? | Is a rabies vaccine necessary after a scratch from a dog, even if there was no bleeding? | Is an injection necessary after a dog scratch with no bleeding? |
| raat ko pair me kuch chubha, saanp tha ya nahi pata nahi, kaise pehchane | Did something sting your foot last night, and how do you determine if it was a snake? | How can I tell if the tingling in my leg at night was a snake bite? | How do I determine if a nighttime foot puncture was a snake bite? | How can I tell if I was bitten by a snake on my leg last night? |
| garbhvati mahila ke pairon me sujan aur tez sir dard hai, koi khatra hai kya | Is swelling in the feet and a severe headache during pregnancy dangerous? | A pregnant woman has swelling in her feet and severe headache—any danger? | Is swelling in the feet and a severe headache during pregnancy dangerous? | Is swelling in the feet and severe headache dangerous for a pregnant woman? |
| बच्चे को डेढ़ महीने पर कौन से टीके लगते हैं? | Which vaccines are given to a baby at one and a half months? | What vaccines are given to a child at one and a half months? | Which vaccines are given to a baby at one and a half months? | Which vaccines are given to a child at one and a half months? |
| teeka lagne ke baad bachche ko halka bukhar aa gaya, kya ye normal hai | Is a mild fever normal after a vaccination? | Is a mild bukhar normal in a child after teeka? | Is a mild fever normal after a vaccine? | Is it normal for a child to have a mild fever after vaccination? |
| khana khane ke baad bhi baar baar bhookh aur pyaas lagti hai aur wajan ghat raha hai | After eating, do you still experience frequent hunger and thirst, and is your weight decreasing? | Why do I feel repeated bhookh and pyaas after eating while my wajan keeps decreasing? | Do you experience frequent hunger and thirst even after eating, along with weight loss? | Why do I feel constant hunger and thirst and experience weight loss after eating? |
| सीने में दर्द और सांस फूल रही है, क्या दिल का दौरा हो सकता है? | Could chest pain and shortness of breath indicate a myocardial infarction? | Chest pain and shortness of breath—could it be a heart attack? | Could chest pain and shortness of breath be a myocardial infarction? | Chest pain and shortness of breath—could it be a heart attack? |
| dengue me platelets bahut kam ho gaye, ghabrane ki baat hai kya | Are low platelets in dengue a cause for concern? | Is it concerning that my dengue has caused my platelets to become very low? | Is a low platelet count in dengue cause for concern? | Is a very low platelet count in dengue a cause for concern? |
| गर्मियों में बुजुर्गों और छोटे बच्चों को गर्मी से कैसे बचाएं? | How do you protect elderly people and young children from heatstroke during summer? | How can we protect the elderly and young children from heat in summer? | How can elderly people and young children be protected from heat stroke? | How can we protect the elderly and young children from heat in summer? |
| chhote bachche ko loose motion me khana dena band kar dein kya | Should food be stopped during diarrhea in a small child? | Should we stop feeding a small child during loose motion? | Should I stop feeding a young child with diarrhoea? | Should we stop feeding a small child with diarrhoea? |
| मलेरिया की दवा बीच में छोड़ दें तो क्या होगा? | What happens if malaria medication is stopped mid-treatment? | What happens if you stop malaria medication halfway? | What happens if malaria medication is stopped early? | What happens if I stop malaria medication halfway? |
| chikungunya aur dengue me fark kaise pata kare | How do you differentiate between chikungunya and dengue? | How can you tell the difference between chikungunya and dengue? | How do you tell the difference between chikungunya and dengue? | How can you tell the difference between chikungunya and dengue? |
| hepatitis B ka pehla injection naye bachche ko kab lagta hai | When does a newborn receive their first hepatitis B injection? | When is the first hepatitis B injection given to a newborn? | When does a newborn receive the first hepatitis B vaccine? | When is the first hepatitis B injection given to a newborn? |
| खांसी में बलगम के साथ खून आ रहा है, क्या करें? | With a cough producing bloody sputum, what should be done? | Cough with phlegm and blood—what should I do? | What should I do if I am coughing up blood with mucus? | Cough with blood in sputum, what should I do? |
| aanganwadi didi ne khoon ki jaanch karane ko kaha, hemoglobin kitna hona chahiye | My Aanganwadi worker told me to get a blood test, what should my hemoglobin level be? | Aanganwadi didi asked for a blood test; what should the hemoglobin be? | What is the normal hemoglobin level? | What should the hemoglobin level be? |
| kaatne wale kutte ko 10 din tak dekhte rehne ko kyu bolte hain | Why is 10-day observation recommended after a dog bite? | Why is a 10‑day observation of the biting dog required? | Why is observation for ten days recommended after a bite from a dog? | Why should the biting dog be observed for 10 days? |
| बच्चे के जन्म के बाद पहले घंटे में माँ का दूध पिलाना क्यों ज़रूरी है? | Why is colostrum feeding important in the first hour after a baby is born? | Why is giving mother’s milk to the baby in the first hour after birth important? | Why is breastfeeding important in the first hour after a baby is born? | Why is giving mother's milk to the baby in the first hour after birth important? |
