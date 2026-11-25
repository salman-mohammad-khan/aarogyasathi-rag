# S2 retrieval bake-off

27 topics x 3 languages = 81 questions. hit@5 / MRR@10.

| Method | Query | English | Hindi | Hinglish | All |
|---|---|---|---|---|---|
| bm25 | as typed | 0.93 / 0.72 | 0.00 / 0.00 | 0.44 / 0.25 | 0.46 / 0.32 |
| bm25 | rewrite gemma-3-27b | 0.93 / 0.72 | 0.85 / 0.66 | 0.81 / 0.59 | 0.86 / 0.65 |
| bm25 | rewrite gpt-oss-120b | 0.93 / 0.72 | 0.85 / 0.65 | 0.78 / 0.57 | 0.85 / 0.65 |
| bm25 | rewrite gemma-3-27b+glossary | 0.93 / 0.72 | 0.93 / 0.73 | 0.93 / 0.67 | 0.93 / 0.71 |
| bm25 | rewrite gpt-oss-120b+glossary | 0.93 / 0.72 | 0.96 / 0.75 | 0.96 / 0.76 | 0.95 / 0.74 |
| e5-base | as typed | 1.00 / 0.89 | 0.74 / 0.61 | 0.33 / 0.24 | 0.69 / 0.58 |
| e5-base+bm25 | as typed | 1.00 / 0.81 | 0.67 / 0.52 | 0.37 / 0.29 | 0.68 / 0.54 |
| e5-base | rewrite gemma-3-27b | 1.00 / 0.89 | 0.96 / 0.86 | 0.93 / 0.78 | 0.96 / 0.85 |
| e5-base+bm25 | rewrite gemma-3-27b | 1.00 / 0.81 | 0.93 / 0.75 | 0.93 / 0.72 | 0.95 / 0.76 |
| e5-base | rewrite gpt-oss-120b | 1.00 / 0.89 | 0.93 / 0.77 | 0.89 / 0.74 | 0.94 / 0.80 |
| e5-base+bm25 | rewrite gpt-oss-120b | 1.00 / 0.81 | 0.89 / 0.77 | 0.96 / 0.71 | 0.95 / 0.76 |
| e5-base | rewrite gemma-3-27b+glossary | 1.00 / 0.89 | 1.00 / 0.85 | 1.00 / 0.86 | 1.00 / 0.87 |
| e5-base+bm25 | rewrite gemma-3-27b+glossary | 1.00 / 0.81 | 1.00 / 0.85 | 1.00 / 0.85 | 1.00 / 0.83 |
| e5-base | rewrite gpt-oss-120b+glossary | 1.00 / 0.89 | 1.00 / 0.84 | 1.00 / 0.85 | 1.00 / 0.86 |
| e5-base+bm25 | rewrite gpt-oss-120b+glossary | 1.00 / 0.81 | 0.96 / 0.85 | 0.96 / 0.83 | 0.97 / 0.83 |
| labse | as typed | 0.81 / 0.59 | 0.74 / 0.52 | 0.41 / 0.24 | 0.65 / 0.45 |
| labse+bm25 | as typed | 1.00 / 0.75 | 0.56 / 0.44 | 0.52 / 0.29 | 0.69 / 0.50 |
| labse | rewrite gemma-3-27b | 0.81 / 0.59 | 0.81 / 0.67 | 0.78 / 0.56 | 0.80 / 0.61 |
| labse+bm25 | rewrite gemma-3-27b | 1.00 / 0.75 | 0.93 / 0.77 | 0.89 / 0.73 | 0.94 / 0.75 |
| labse | rewrite gpt-oss-120b | 0.81 / 0.59 | 0.74 / 0.61 | 0.74 / 0.59 | 0.77 / 0.60 |
| labse+bm25 | rewrite gpt-oss-120b | 1.00 / 0.75 | 0.89 / 0.67 | 0.81 / 0.63 | 0.90 / 0.69 |
| labse | rewrite gemma-3-27b+glossary | 0.81 / 0.59 | 0.85 / 0.67 | 0.81 / 0.63 | 0.83 / 0.63 |
| labse+bm25 | rewrite gemma-3-27b+glossary | 1.00 / 0.75 | 1.00 / 0.81 | 1.00 / 0.75 | 1.00 / 0.77 |
| labse | rewrite gpt-oss-120b+glossary | 0.81 / 0.59 | 0.81 / 0.62 | 0.81 / 0.61 | 0.81 / 0.61 |
| labse+bm25 | rewrite gpt-oss-120b+glossary | 1.00 / 0.75 | 0.96 / 0.72 | 0.89 / 0.72 | 0.95 / 0.73 |
| titan-v2 | as typed | 0.96 / 0.86 | 0.81 / 0.62 | 0.48 / 0.30 | 0.75 / 0.59 |
| titan-v2+bm25 | as typed | 1.00 / 0.84 | 0.67 / 0.49 | 0.56 / 0.35 | 0.74 / 0.56 |
| titan-v2 | rewrite gemma-3-27b | 0.96 / 0.86 | 0.93 / 0.85 | 0.93 / 0.83 | 0.94 / 0.85 |
| titan-v2+bm25 | rewrite gemma-3-27b | 1.00 / 0.84 | 0.93 / 0.81 | 0.89 / 0.79 | 0.94 / 0.81 |
| titan-v2 | rewrite gpt-oss-120b | 0.96 / 0.86 | 0.89 / 0.79 | 0.81 / 0.73 | 0.89 / 0.79 |
| titan-v2+bm25 | rewrite gpt-oss-120b | 1.00 / 0.84 | 0.93 / 0.79 | 0.85 / 0.75 | 0.93 / 0.80 |
| titan-v2 | rewrite gemma-3-27b+glossary | 0.96 / 0.86 | 0.96 / 0.86 | 0.96 / 0.87 | 0.96 / 0.86 |
| titan-v2+bm25 | rewrite gemma-3-27b+glossary | 1.00 / 0.84 | 1.00 / 0.92 | 1.00 / 0.89 | 1.00 / 0.88 |
| titan-v2 | rewrite gpt-oss-120b+glossary | 0.96 / 0.86 | 0.96 / 0.91 | 0.96 / 0.88 | 0.96 / 0.88 |
| titan-v2+bm25 | rewrite gpt-oss-120b+glossary | 1.00 / 0.84 | 0.93 / 0.88 | 0.93 / 0.88 | 0.95 / 0.87 |

## Questions the hybrid methods missed (no correct chunk in the top 5)

- **e5-base+bm25 | as typed**: dengue-mosquito-breeding (hi), dengue-mosquito-breeding (hinglish), malaria-bednets (hinglish), tb-symptoms (hi), tb-symptoms (hinglish), tb-treatment-complete (hi), ors-preparation (hinglish), diarrhoea-zinc (hi), diarrhoea-danger-signs (hinglish), pneumonia-fast-breathing (hi), pneumonia-fast-breathing (hinglish), snakebite-first-aid (hinglish), snakebite-tourniquet (hi), snakebite-tourniquet (hinglish), dog-bite-wash (hinglish), heatstroke-signs (hi), heatstroke-signs (hinglish), heatstroke-cooling (hinglish), anaemia-symptoms (hinglish), pregnancy-danger-signs (hinglish), newborn-vaccines-birth (hi), newborn-vaccines-birth (hinglish), measles-vaccine-age (hinglish), hypertension-salt (hinglish), diabetes-symptoms (hi), diabetes-symptoms (hinglish)
- **e5-base+bm25 | rewrite gemma-3-27b**: heatstroke-signs (hi), heatstroke-signs (hinglish), anaemia-symptoms (hi), anaemia-symptoms (hinglish)
- **e5-base+bm25 | rewrite gpt-oss-120b**: heatstroke-signs (hi), heatstroke-signs (hinglish), anaemia-symptoms (hi), diabetes-symptoms (hi)
- **e5-base+bm25 | rewrite gemma-3-27b+glossary**: none
- **e5-base+bm25 | rewrite gpt-oss-120b+glossary**: snakebite-tourniquet (hi), diabetes-symptoms (hinglish)
- **labse+bm25 | as typed**: dengue-mosquito-breeding (hi), chikungunya-joint-pain (hi), malaria-bednets (hi), malaria-bednets (hinglish), tb-symptoms (hi), diarrhoea-danger-signs (hinglish), snakebite-first-aid (hinglish), snakebite-tourniquet (hi), snakebite-tourniquet (hinglish), dog-bite-wash (hi), dog-bite-wash (hinglish), rabies-vaccine (hi), heatstroke-signs (hi), heatstroke-signs (hinglish), heatstroke-cooling (hinglish), anaemia-symptoms (hi), anaemia-symptoms (hinglish), pregnancy-danger-signs (hinglish), newborn-vaccines-birth (hinglish), measles-vaccine-age (hi), measles-vaccine-age (hinglish), hypertension-salt (hinglish), diabetes-symptoms (hi), diabetes-symptoms (hinglish), typhoid-spread (hi)
- **labse+bm25 | rewrite gemma-3-27b**: diarrhoea-danger-signs (hinglish), heatstroke-signs (hi), heatstroke-signs (hinglish), anaemia-symptoms (hi), anaemia-symptoms (hinglish)
- **labse+bm25 | rewrite gpt-oss-120b**: diarrhoea-danger-signs (hinglish), snakebite-tourniquet (hinglish), dog-bite-wash (hinglish), heatstroke-signs (hi), heatstroke-signs (hinglish), anaemia-symptoms (hi), anaemia-symptoms (hinglish), diabetes-symptoms (hi)
- **labse+bm25 | rewrite gemma-3-27b+glossary**: none
- **labse+bm25 | rewrite gpt-oss-120b+glossary**: dengue-mosquito-breeding (hinglish), snakebite-tourniquet (hi), snakebite-tourniquet (hinglish), diabetes-symptoms (hinglish)
- **titan-v2+bm25 | as typed**: malaria-symptoms (hi), malaria-bednets (hinglish), tb-symptoms (hi), tb-symptoms (hinglish), diarrhoea-danger-signs (hinglish), pneumonia-fast-breathing (hi), pneumonia-fast-breathing (hinglish), snakebite-first-aid (hi), snakebite-tourniquet (hinglish), dog-bite-wash (hinglish), rabies-vaccine (hi), heatstroke-signs (hi), heatstroke-signs (hinglish), heatstroke-cooling (hinglish), anaemia-symptoms (hi), anaemia-symptoms (hinglish), newborn-vaccines-birth (hinglish), measles-vaccine-age (hinglish), hypertension-salt (hi), diabetes-symptoms (hi), diabetes-symptoms (hinglish)
- **titan-v2+bm25 | rewrite gemma-3-27b**: dengue-mosquito-breeding (hinglish), heatstroke-signs (hi), heatstroke-signs (hinglish), anaemia-symptoms (hi), anaemia-symptoms (hinglish)
- **titan-v2+bm25 | rewrite gpt-oss-120b**: dengue-mosquito-breeding (hinglish), heatstroke-signs (hi), heatstroke-signs (hinglish), anaemia-symptoms (hi), anaemia-symptoms (hinglish), measles-vaccine-age (hinglish)
- **titan-v2+bm25 | rewrite gemma-3-27b+glossary**: none
- **titan-v2+bm25 | rewrite gpt-oss-120b+glossary**: dengue-mosquito-breeding (hi), dengue-mosquito-breeding (hinglish), snakebite-tourniquet (hi), diabetes-symptoms (hinglish)

## English rewrites used

| Question | gemma-3-27b | gpt-oss-120b | gemma-3-27b+glossary | gpt-oss-120b+glossary |
|---|---|---|---|---|
| डेंगू के लक्षण क्या हैं? | What are the symptoms of dengue? | What are the symptoms of dengue? | What are the symptoms of dengue? | What are the symptoms of dengue? |
| dengue ke lakshan kya hote hain | What are the symptoms of dengue? | What are the symptoms of dengue? | What are the symptoms of dengue? | What are the symptoms of dengue? |
| डेंगू में कौन से खतरे के संकेत हों तो तुरंत अस्पताल जाना चाहिए? | What dengue danger signs require immediate hospitalization? | What danger signs in dengue mean you should go to the hospital right away? | What dengue symptoms require immediate hospitalization? | What danger signs in dengue require immediate hospital admission? |
| dengue me kaun se khatre ke sign ho to turant hospital jana chahiye | What dengue danger signs require immediate hospitalization? | Which danger signs in dengue require immediate hospital visit? | What dengue symptoms require immediate hospitalization? | In dengue, which danger signs require immediate hospital admission? |
| घर के आसपास डेंगू के मच्छरों को पनपने से कैसे रोकें? | How do you prevent Aedes mosquitoes from breeding near your home to reduce the risk of dengue? | How can you stop dengue mosquitoes from breeding around your home? | How can I prevent mosquitoes that carry dengue fever from breeding near my home? | How can I stop dengue mosquitoes from breeding around my house? |
| ghar ke aas paas dengue ke machhar paida hone se kaise roke | How do you prevent dengue mosquitoes from breeding near the home? | How can we stop dengue mosquitoes from breeding near the house? | How can I prevent mosquito breeding around my home to avoid dengue? | How can I prevent dengue mosquitoes from breeding near my home? |
| चिकनगुनिया में जोड़ों का दर्द कितने दिन रहता है? | How many days does arthralgia last in chikungunya? | In chikungunya, how many days does joint pain last? | How long does joint pain last with chikungunya? | How many days does joint pain last in chikungunya? |
| chikungunya me jodo ka dard kitne din tak rehta hai | How long does chikungunya joint pain last? | In chikungunya, how many days does joint pain last? | How long does joint pain last with chikungunya? | How many days does joint pain last in chikungunya? |
| मलेरिया बुखार के लक्षण क्या होते हैं? | What are the symptoms of malaria fever? | What are the symptoms of malaria fever? | What are the symptoms of malaria fever? | What are the symptoms of malaria fever? |
| malaria bukhar ke lakshan kya hote hai | What are the symptoms of malaria fever? | What are the symptoms of malaria bukhar? | What are the symptoms of malaria fever? | What are the symptoms of malaria fever? |
| क्या मच्छरदानी से मलेरिया से बचाव होता है? | Does a mosquito net prevent malaria? | Does a mosquito net protect against malaria? | Does a mosquito net prevent malaria? | Does a mosquito net protect against malaria? |
| kya machhardani lagane se malaria se bachav hota hai | Does using a mosquito net prevent malaria? | Does applying machhardeni prevent malaria? | Does using a mosquito net prevent malaria? | Does using a mosquito net prevent malaria? |
| तीन हफ्ते से खांसी है और वजन घट रहा है, क्या यह टीबी हो सकती है? | Could a three-week cough and weight loss be tuberculosis? | I've had a cough for three weeks and am losing weight—could it be TB? | Could a cough lasting three weeks and weight loss indicate tuberculosis? | Cough for three weeks and weight loss, could it be TB? |
| teen hafte se khansi hai aur wajan kam ho raha hai, kya ye TB ho sakta hai | Do you have a cough for two weeks and weight loss, could it be tuberculosis? | Teen has had a cough for a week and is losing weight; could this be TB? | Could a cough lasting three weeks and weight loss indicate tuberculosis? | I've had a cough for three weeks and am losing weight; could this be TB? |
| टीबी की दवा पूरा कोर्स क्यों लेना ज़रूरी है? | Why is completing the full course of tuberculosis medication necessary? | Why is it necessary to complete the full course of TB medication? | Why is it necessary to complete the full course of tuberculosis medication? | Why is it necessary to complete the full TB medication course? |
| TB ki dawai ka pura course lena kyu zaroori hai | Why is completing the full course of tuberculosis medication necessary? | Why is it necessary to take the full course of TB medication? | Why is completing the full course of tuberculosis medication important? | Why is it important to complete the full course of TB medication? |
| घर पर ओआरएस का घोल कैसे बनाएं? | How do you make oral rehydration solution at home? | How do I make an ORS solution at home? | How do I make oral rehydration solution at home? | How do I make an ORS solution at home? |
| ghar par ORS ka ghol kaise banate hain | How do you make an ORS solution at home? | How do you make ORS solution at home? | How do you make an oral rehydration solution at home? | How do you make ORS solution at home? |
| बच्चों को दस्त में जिंक क्यों दिया जाता है? | Why is zinc given for diarrhea in children? | Why is zinc given to children with diarrhea? | Why is zinc given for diarrhoea in children? | Why is zinc given to children with diarrhoea? |
| bacche ko dast me zinc kyu dete hain | Why is zinc given for diarrhea in children? | Why give zinc to a child with diarrhea? | Why is zinc given for diarrhoea in children? | Why is zinc given to a child with diarrhoea? |
| दस्त वाले बच्चे को डॉक्टर के पास कब ले जाना चाहिए? | When should a child with diarrhea be taken to a doctor? | When should a child with diarrhea be taken to the doctor? | When should a child with diarrhoea be taken to a doctor? | When should a child with diarrhoea be taken to the doctor? |
| dast wale bacche ko doctor ke paas kab le jana chahiye | When should a child with a rash be taken to the doctor? | When should a child with dast be taken to the doctor? | When should a child with diarrhoea be taken to a doctor? | When should a child with diarrhoea be taken to the doctor? |
| कैसे पता करें कि बच्चे को निमोनिया है? | How do you know if a child has pneumonia? | How can you tell if a child has pneumonia? | How can I tell if a child has pneumonia? | How can you tell if a child has pneumonia? |
| kaise pata kare ki bacche ko pneumonia hai | How do I know if a child has pneumonia? | How can you tell if a child has pneumonia? | How do I know if a child has pneumonia? | How can you tell if a child has pneumonia? |
| सांप काटने पर तुरंत क्या प्राथमिक उपचार करें? | What first aid should be given immediately for a snake bite? | What first aid should be done immediately after a snake bite? | What first aid should be given immediately for a snake bite? | What immediate first aid should be given for a snake bite? |
| saanp kaatne par turant kya first aid kare | What first aid should be given immediately for a snake bite? | What first aid should be done immediately after a snake bite? | What immediate first aid should be given for a snake bite? | What immediate first aid should be given for a snake bite? |
| सांप काटने पर क्या कसकर पट्टी बांधनी चाहिए या घाव काटना चाहिए? | Should a tight tourniquet be applied or the wound excised after a snakebite? | After a snake bite, should you apply a tight bandage or cut the wound? | Should a tight bandage be applied or the wound cut after a snake bite? | Should a snake bite be tightly bandaged or cut open? |
| saanp kaatne par kya kas ke kapda bandhna chahiye ya ghaav kaatna chahiye | Should a constricting bandage or incision be made after a snakebite? | After a snake bite, should you tightly wrap the cloth or cut the wound? | Should a tight bandage be applied or the wound cut after a snake bite? | After a snake bite, should the cloth be tightly wrapped or the wound cut? |
| कुत्ते के काटने के तुरंत बाद क्या करना चाहिए? | What should be done immediately after a dog bite? | What should be done immediately after a dog bite? | What should be done immediately after a dog bite? | What should be done immediately after a dog bite? |
| kutte ke kaatne ke turant baad kya karna chahiye | What should be done immediately after a dog bite? | What should be done right after a dog bite? | What should be done immediately after a dog bite? | What should be done immediately after a dog bite? |
| कुत्ते के काटने के बाद रेबीज़ के कितने इंजेक्शन लगते हैं? | How many rabies injections are needed after a dog bite? | How many rabies injections are needed after a dog bite? | How many rabies injections are needed after a dog bite? | How many rabies injections are given after a dog bite? |
| kutte ke kaatne ke baad rabies ke kitne injection lagte hain | How many rabies injections are needed after a dog bite? | How many rabies injections are needed after a dog bite? | How many rabies injections are needed after a dog bite? | How many rabies injections are required after a dog bite? |
| लू लगने के लक्षण क्या हैं? | What are the symptoms of fever? | What are the symptoms of लू? | What are the symptoms of heat stroke? | What are the symptoms of heat stroke? |
| loo lagne ke lakshan kya hai | What are the symptoms of leukemia? | What are the symptoms of loo? | What are the symptoms of heat stroke? | What are the symptoms of heat stroke? |
| गर्मी में बेहोश हुए व्यक्ति को ठंडा कैसे करें? | How do you cool someone who has fainted in the heat? | How do you cool an unconscious person in heat? | How do you cool someone who has fainted from heat stroke? | How do you cool a person who has fainted from heat stroke? |
| garmi me behosh hue aadmi ko thanda kaise kare | How do you cool down a person who has fainted from the heat? | How do you cool a man who is behosh in heat? | How do you cool down someone who has fainted from heat stroke? | How do you cool a person who has fainted from heat stroke? |
| खून की कमी के लक्षण क्या हैं? | What are the symptoms of anemia? | What are the symptoms of anemia? | What are the symptoms of anaemia? | What are the symptoms of anaemia? |
| khoon ki kami ke lakshan kya hai | What are the symptoms of anemia? | What are the symptoms of khoon ki kami? | What are the symptoms of anaemia? | What are the symptoms of anaemia? |
| आयरन वाले भोजन कौन से हैं? | Which foods contain iron? | Which foods contain iron? | What foods contain iron? | Which foods contain iron? |
| iron wale khane kaun kaun se hain | What foods contain iron? | Which foods contain iron? | What foods contain iron? | Which foods contain iron? |
| गर्भावस्था में कौन से खतरे के लक्षण दिखें तो अस्पताल जाएं? | During pregnancy, what danger signs warrant hospitalization? | गर्भावस्था में कौन से खतरे के लक्षण दिखें तो अस्पताल जाना चाहिए? | What danger signs during pregnancy require hospital care? | What danger signs during pregnancy require a hospital visit? |
| pregnancy me kaun se khatre ke lakshan dikhe to hospital jaye | What danger signs during pregnancy require hospitalization? | In pregnancy, which danger signs require a hospital visit? | What danger signs during pregnancy require a hospital visit? | What danger signs in pregnancy require a hospital visit? |
| नवजात शिशु को जन्म के समय कौन से टीके लगते हैं? | Which vaccines are given to a newborn at birth? | What vaccines are given to a newborn at birth? | Which vaccines are given to a newborn baby at birth? | Which vaccines are given to a newborn at birth? |
| navjaat bacche ko janam ke samay kaun se teeke lagte hain | Which vaccines are given to a newborn at birth? | Which teeke are given to a navjaat baccha at birth? | Which vaccines are given to a newborn baby at birth? | Which vaccines are given to a newborn at birth? |
| खसरे का टीका किस उम्र में लगता है? | At what age is the measles vaccine administered? | At what age is the measles vaccine given? | At what age is the measles vaccine given? | At what age is the measles vaccine given? |
| khasre ka teeka kis umar me lagta hai | At what age is the measles vaccine given? | At what age is the khasre ka teeka given? | At what age is the measles vaccine given? | At what age is the measles vaccine given? |
| बिना दवा के हाई ब्लड प्रेशर कैसे कंट्रोल करें? | How do you control hypertension without medication? | How can you control high blood pressure without medication? | How can I control high blood pressure without medication? | How can I control high blood pressure without medication? |
| bina dawai ke high BP kaise control kare | How do you control high BP without medication? | How can you control high BP without medicine? | How can I control high blood pressure without medication? | How can I control high blood pressure without medication? |
| शुगर की बीमारी के शुरुआती लक्षण क्या हैं? | What are the early symptoms of diabetes mellitus? | What are the early symptoms of शुगर? | What are the early symptoms of diabetes? | What are the early symptoms of diabetes? |
| sugar ki bimari ke shuruaati lakshan kya hai | What are the early symptoms of diabetes mellitus? | What are the early symptoms of diabetes? | What are the early symptoms of diabetes? | What are the early symptoms of sugar? |
| टाइफाइड कैसे फैलता है? | How does typhoid spread? | How does typhoid spread? | How is typhoid fever transmitted? | How does typhoid spread? |
| typhoid kaise failta hai | How does typhoid spread? | How does typhoid spread? | How is typhoid transmitted? | How is typhoid spread? |
| हेपेटाइटिस बी एक इंसान से दूसरे में कैसे फैलता है? | How does Hepatitis B spread from person to person? | How does hepatitis B spread from one person to another? | How is hepatitis B transmitted from person to person? | How is hepatitis B transmitted from one person to another? |
| hepatitis B ek insaan se dusre me kaise failta hai | How does hepatitis B spread from one person to another? | How does hepatitis B spread from one person to another? | How is hepatitis B transmitted from person to person? | How does hepatitis B spread from one person to another? |
