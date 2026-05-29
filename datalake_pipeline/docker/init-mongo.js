// ==========================================================================
// init-mongo.js
// Initialisation de MongoDB pour le projet RAG Medical
// Execute automatiquement au premier demarrage du container
// ==========================================================================

// Se connecter a la base medrag
db = db.getSiblingDB('medrag');

// Creer un utilisateur dedie pour l'application
db.createUser({
    user: 'medrag_app',
    pwd: 'medrag_app_2024',
    roles: [
        { role: 'readWrite', db: 'medrag' }
    ]
});

// ==========================================================================
// Collection : health_centers
// Centres de sante FINESS avec geolocalisation
// ==========================================================================
db.createCollection('health_centers');

// Index geospatial 2dsphere pour les requetes de proximite
// Permet : db.health_centers.find({ location: { $near: { $geometry: { type: "Point", coordinates: [lon, lat] }, $maxDistance: 20000 } } })
db.health_centers.createIndex(
    { "location": "2dsphere" },
    { name: "idx_location_2dsphere" }
);

// Index texte pour la recherche full-text sur le nom et la categorie
db.health_centers.createIndex(
    { "name": "text", "category": "text", "specialty": "text", "city": "text" },
    { name: "idx_text_search", default_language: "french" }
);

// Index sur le code categorie (pour le filtrage par type d'etablissement)
db.health_centers.createIndex(
    { "category_code": 1 },
    { name: "idx_category_code" }
);

// Index sur le departement (pour le filtrage geographique large)
db.health_centers.createIndex(
    { "department": 1 },
    { name: "idx_department" }
);

// Index compose pour les requetes combinant categorie + proximite
db.health_centers.createIndex(
    { "category_code": 1, "location": "2dsphere" },
    { name: "idx_category_location" }
);

// Index sur le code postal
db.health_centers.createIndex(
    { "postal_code": 1 },
    { name: "idx_postal_code" }
);

// ==========================================================================
// Collection : recommendations_log (suivi des recommandations)
// ==========================================================================
db.createCollection('recommendations_log');

db.recommendations_log.createIndex(
    { "created_at": -1 },
    { name: "idx_log_date", expireAfterSeconds: 2592000 }  // TTL 30 jours
);

// ==========================================================================
// Verification
// ==========================================================================
print('=== MongoDB medrag initialise avec succes ===');
print('Base     : medrag');
print('User app : medrag_app');
print('Collections : health_centers, recommendations_log');
print('Index : 2dsphere (geoloc), text (recherche), category_code, department');
print('');
print('Exemple de requete geospatiale :');
print('  db.health_centers.find({');
print('    location: { $near: {');
print('      $geometry: { type: "Point", coordinates: [-1.6743, 48.1173] },');
print('      $maxDistance: 10000');
print('    }},');
print('    category_code: { $in: ["355", "146", "101"] }');
print('  }).limit(5)');
