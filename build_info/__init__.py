"""Module for extract the JFrog Artifactory Build Info json: https://github.com/JFrogDev/build-info"""

"""
/* List of build modules */
  "modules" : [ { // The build's first module
    "properties" : { // Module properties
      "project.build.sourceEncoding" : "UTF-8"
    },
    "id" : "org.jfrog.test:multi2:4.2-SNAPSHOT", // Module ID
    /* List of module artifacts */
    "artifacts" : [ {
      "type" : "jar",
      "sha1" : "2ed52ad1d864aec00d7a2394e99b3abca6d16639",
      "md5" : "844920070d81271b69579e17ddc6715c",
      "name" : "multi2-4.2-SNAPSHOT.jar"
    }, {
      "type" : "pom",
      "sha1" : "e8e9c7d790191f4a3df3a82314ac590f45c86e31",
      "md5" : "1f027d857ff522286a82107be9e807cd",
      "name" : "multi2-4.2-SNAPSHOT.pom"
    } ],
    /* List of module dependencies */
    "dependencies" : [ {
      "type" : "jar",
      "sha1" : "99129f16442844f6a4a11ae22fbbee40b14d774f",
      "md5" : "1f40fb782a4f2cf78f161d32670f7a3a",
      "id" : "junit:junit:3.8.1",
      "scopes" : [ "test" ]
    } ]
  }, { // The build's second module
    "properties" : { // Module properties
      "project.build.sourceEncoding" : "UTF-8"
    },
    "id" : "org.jfrog.test:multi3:4.2-SNAPSHOT", // Module ID
    /* List of module artifacts */
    "artifacts" : [ { // Module artifacts
      "type" : "war",
      "sha1" : "df8e7d7b94d5ec9db3bfc92e945c7ff4e2391c7c",
      "md5" : "423c24f4c6e259f2774921b9d874a649",
      "name" : "multi3-4.2-SNAPSHOT.war"
    }, {
      "type" : "pom",
      "sha1" : "656330c5045130f214f954643fdc4b677f4cf7aa",
      "md5" : "b0afa67a9089b6f71b3c39043b18b2fc",
      "name" : "multi3-4.2-SNAPSHOT.pom"
    } ],
    /* List of module dependencies */
    "dependencies" : [ {
      "type" : "jar",
      "sha1" : "a8762d07e76cfde2395257a5da47ba7c1dbd3dce",
      "md5" : "b6a50c8a15ece8753e37cbe5700bf84f",
      "id" : "commons-io:commons-io:1.4",
      "scopes" : [ "compile" ]
    }, {
      "type" : "jar",
      "sha1" : "342d1eb41a2bc7b52fa2e54e9872463fc86e2650",
      "md5" : "2a666534a425add50d017d4aa06a6fca",
      "id" : "org.codehaus.plexus:plexus-utils:1.5.1",
      "scopes" : [ "compile" ]
    }, {
      "type" : "jar",
      "sha1" : "449ea46b27426eb846611a90b2fb8b4dcf271191",
      "md5" : "25c0752852205167af8f31a1eb019975",
      "id" : "org.springframework:spring-beans:2.5.6",
      "scopes" : [ "compile" ]
    } ]
  } ],
"""