# CLAUDE.md — Contexte projet MedRAG

## 1. Présentation du projet

Le projet s'appelle actuellement **MedRAG**.

C'est un outil web d'aide au diagnostic, de pré-diagnostique médical conversationnel et d'accompagnement du patient. L'objectif n'est pas de remplacer un médecin, mais d'aider le patient à mieux décrire son état, suivre l'évolution de ses symptômes, identifier les signes d'alerte, préparer une consultation, et être orienté vers le professionnel ou l'établissement de santé le plus adapté.

L'outil doit pouvoir proposer plusieurs hypothèses médicales possibles, aider à structurer le parcours patient, puis recommander une orientation : domicile, pharmacie, médecin généraliste, spécialiste, urgences ou SAMU selon le niveau de risque.

Le projet est destiné en priorité aux patients. Une évolution possible est de créer une interface ou un usage secondaire pour les médecins, afin qu'ils puissent recevoir un résumé structuré du parcours patient avant la consultation.

## 2. Positionnement médical obligatoire

L'application peut :

* proposer des hypothèses de pathologies possibles ;
* expliquer pourquoi certaines pistes sont envisagées ;
* poser des questions complémentaires ;
* identifier des signes d'alerte ;
* recommander une orientation médicale ;
* aider à préparer une consultation ;
* générer un résumé patient exploitable par un médecin ou un pharmacien ;
* suggérer des établissements de santé ou pharmacies proches.

L'application ne doit jamais :

* affirmer un diagnostic définitif ;
* dire au patient qu'il n'a pas besoin d'un professionnel en cas de doute ;
* minimiser un symptôme grave ;
* remplacer une consultation médicale ;
* prescrire un traitement ;
* modifier ou arrêter un traitement existant ;
* donner une conduite dangereuse sans recommander un avis médical.

Formulation à privilégier :

> “Les informations suivantes constituent une aide à l'orientation et ne remplacent pas l'avis d'un professionnel de santé.”

Préférer les formulations :

* “hypothèses possibles”
* “pistes à discuter avec un professionnel”
* “orientation recommandée”
* “signes nécessitant une consultation rapide”

Éviter :

* “vous avez cette maladie”
* “diagnostic confirmé”
* “pas besoin de consulter”
* “traitement à prendre”

## 3. Vision fonctionnelle

L'application doit évoluer vers un assistant patient complet avec :

1. Chat médical conversationnel
2. Prédiagnostic avec 2 à 4 hypothèses possibles
3. Questions ciblées posées par l'IA
4. Détection des signes d'alerte
5. Orientation vers le bon niveau de soin
6. Recommandation de médecins, pharmacies ou établissements proches
7. Carte affichée uniquement au moment de la recommandation de soins
8. Dossier patient
9. Historique des symptômes
10. Timeline d'évolution
11. Préparation de consultation
12. Résumé exportable ou transmissible au médecin/pharmacien
13. Possibilité de préparer un mail pour le professionnel de santé
14. Suivi hygiéno-diététique pour certaines maladies chroniques
15. Prise en compte du mode de vie, des habitudes alimentaires, des facteurs déclenchants, calmants et aggravants

## 4. Fonctionnalités importantes inspirées des retours médicaux

L'outil doit tenir compte des éléments suivants :

* histoire de la maladie ;
* date et moment d'apparition des symptômes ;
* évolution des symptômes ;
* symptômes associés ;
* intensité ;
* fréquence ;
* durée ;
* facteurs déclenchants ;
* facteurs calmants ;
* facteurs aggravants ;
* habitudes alimentaires ;
* mode de vie(peut etre collecter à l apremière connexion et stocker dans le profil patient et consulter à chaque connexion du patient et enrichie et mis à jour au cours des discussions) ;
* antécédents (peut etre collecter à l apremière connexion et stocker dans le profil patient et consulter à chaque connexion du patient) ;
* traitements en cours(peut etre collecter à l apremière connexion et stocker dans le profil patient et consulter à chaque connexion du patient, et pour celui-ci être redemander à chaque conersation si besoin, par exemple si lors de la première connexion le patient dit je suis un traitment constant pour tel pathologie ca veut dire que c'est son traitment en cours pour toujours il faudra donc demander s'il ya un nouveau, si celui la est arreté et mettre à jour la base) ;
* allergies si disponibles(peut etre collecter à l apremière connexion et stocker dans le profil patient et consulter à chaque connexion du patient);
* contexte familial ou environnemental;
* suivi de maladies chroniques comme diabète, hypertension artérielle, asthme.

Le patient ne doit pas forcément remplir un formulaire classique. Ces informations doivent être collectées naturellement dans la conversation avec l'IA.

## 5. Stack technique actuelle

Frontend :

* React 18
* Vite
* React Leaflet
* React Markdown
* CSS pur

Backend :

* FastAPI
* Uvicorn
* Pydantic
* Authentification avec bcrypt
* Sessions avec tokens

Bases de données :

* PostgreSQL 16
* pgvector
* MongoDB 7 avec index géospatial 2dsphere

IA / RAG :

* Claude avec tool use
* Prompt caching
* sentence-transformers
* modèle intfloat/multilingual-e5-base
* architecture RAG avec plusieurs pools sémantiques

Infrastructure :

* Docker Compose
* pgAdmin
* mongo-express

## 6. Architecture RAG actuelle

Le système utilise actuellement plusieurs sources :

1. Pathologies issues de DDXPlus
2. Patients similaires issus de DDXPlus
3. Cas cliniques issus de MTSamples
4. Établissements de santé issus de FINESS

L'architecture RAG actuelle doit être conservée comme base, mais elle peut être enrichie.

Ne pas supprimer l'existant sans validation.

Améliorations possibles à étudier :

* meilleure pondération des pools ;
* ajout d'un re-ranker ;
* meilleure gestion français/anglais ;
* distinction entre recherche médicale, recherche d'orientation et recherche géographique ;
* enrichissement avec des sources médicales fiables ;
* ajout d'un module de génération de résumé patient ;
* ajout d'un module de suivi des symptômes.

## 7. Règles pour Claude Code

Avant toute modification importante :

* expliquer ce qui va être modifié ;
* demander validation ;
* éviter les gros refactorings inutiles ;
* conserver un code simple et compréhensible ;
* privilégier une architecture claire plutôt qu'une complexité excessive.

Quand Claude Code écrit du code :

* utiliser des noms de fichiers et fonctions explicites ;
* garder le code lisible ;
* ajouter des commentaires utiles mais pas excessifs ;
* éviter les abstractions trop compliquées ;
* proposer des tests quand c'est pertinent ;
* ne pas casser l'existant ;
* vérifier les impacts frontend/backend/base de données.

Quand une fonctionnalité est proposée :

* expliquer son intérêt utilisateur ;
* expliquer son intérêt médical ou méthodologique ;
* expliquer son impact technique ;
* préciser si elle est prioritaire ou secondaire.

## 8. Règles UI / UX

L'interface actuelle ne satisfait pas encore les attentes.

L'objectif est une interface :

* simple pour le patient ;
* rassurante ;
* moderne ;
* claire ;
* professionnelle ;
* centrée sur le chat ;
* enrichie par un tableau de bord patient ;
* adaptée au web dans un premier temps.

L'application doit éviter de ressembler à un simple chatbot. Elle doit devenir un véritable assistant patient avec :

* espace conversation ;
* dossier patient ;
* historique ;
* timeline des symptômes ;
* panneau de recommandations ;
* carte des professionnels de santé ;
* résumé de consultation.

La carte ne doit pas être affichée en permanence. Elle doit apparaître au moment où l'IA recommande une orientation vers un médecin, une pharmacie, un établissement ou les urgences.

## 9. Pages envisagées

Pages ou sections possibles :

* accueil ;
* inscription ;
* connexion (avec récupération des données pour constitué le profil patient) ;
* tableau de bord patient ;
* chat médical ;
* historique des conversations ;
* dossier patient ;
* suivi des symptômes ;
* timeline d'évolution ;
* recommandations de soins ;
* carte des établissements ;
* résumé de consultation ;
* export ou préparation d'email pour médecin/pharmacien.

L'utilisateur doit avoir un compte, car ses informations médicales et son historique doivent être associés à son profil.

## 10. Rapport et soutenance

Le projet doit être présenté comme :

* un outil d'aide au diagnostic ;
* un assistant patient intelligent ;
* un système RAG médical ;
* un outil de pré-triage et de préparation à la consultation.

Le rapport doit insister sur :

* le besoin médical ;
* les limites des recherches symptomatiques classiques ;
* l'intérêt du RAG ;
* l'intérêt du suivi patient ;
* l'intérêt de l'orientation géographique ;
* la sécurité médicale ;
* les limites éthiques ;
* le fait que l'outil ne remplace pas un médecin.

La soutenance est proche. Il faut donc privilégier les améliorations visibles, cohérentes et défendables académiquement.

## 11. Priorités projet

Priorité 1 :

* clarifier le positionnement médical ;
* améliorer l'interface ;
* enrichir les fonctionnalités patient ;
* structurer le dossier patient ;
* générer un bon résumé de consultation.

Priorité 2 :

* améliorer le RAG ;
* enrichir les sources ;
* améliorer la recherche des établissements ;
* proposer médecins/pharmacies selon l'orientation.

Priorité 3 :

* préparer les évolutions futures ;
* interface médecin ;
* envoi automatique de mail ;
* suivi chronique avancé ;
* conformité plus poussée aux normes de santé.

## 12. Comportement attendu de Claude Code

Claude Code doit agir comme :

* assistant de recherche ;
* architecte logiciel ;
* conseiller produit ;
* designer UI/UX ;
* reviewer technique ;
* assistant de rédaction académique.

Il doit toujours garder en tête que le projet doit être :

* utile pour le patient ;
* crédible médicalement ;
* techniquement simple à défendre ;
* suffisamment riche pour un projet de Master ;
* présentable en soutenance ;
* prudent sur le plan médical.

## 13. Profil patient initial et évolutif

Lors de la première inscription, l'application doit permettre à l'utilisateur de renseigner un profil santé de base. Ce profil sert à contextualiser les futures conversations médicales.

Informations à collecter :
- âge ;
- sexe ;
- département ou localisation approximative ;
- antécédents médicaux ;
- maladies chroniques ;
- traitements en cours ;
- allergies connues ;
- mode de vie ;
- habitudes alimentaires si utiles.

Ces informations doivent être stockées dans le profil patient et consultées lors de chaque nouvelle conversation.

Le profil patient doit être évolutif. Pendant les échanges, l'agent peut demander s'il ya des changemnt en cours par rapport a son profil si besoin biensur, et  si l'utilisateur mentionne une nouvelle allergie, un nouveau traitement, l'arrêt d'un traitement, un antécédent ou une maladie chronique, l'application doit proposer de mettre à jour le profil.

La mise à jour du profil ne doit jamais être automatique sans confirmation explicite de l'utilisateur.

Cas particulier des traitements :
- distinguer les traitements chroniques des traitements temporaires ;
- conserver le statut du traitement : actif, arrêté ou inconnu ;
- conserver la date de début si connue ;
- conserver la date d'arrêt si connue ;
- conserver la dernière date de confirmation ;
- redemander confirmation uniquement lorsque c'est pertinent médicalement.

Objectif : permettre à MedRAG de mieux comprendre le patient dans la durée, sans lui demander de répéter les mêmes informations à chaque conversation.