"""Liste française pour TfidfVectorizer (scikit-learn >=1.6 n'accepte plus stop_words='french')."""

FRENCH_STOP_WORDS: frozenset[str] = frozenset(
    """
    a ai aie aient aies ait alors apres au aucun aucune aux avaient avais avait
    avant avec avons ayant beaucoup bien c car ce ceci cela ces cet cette ceux
    chaque ci comme comment d dans de des deux devrait devront doit donc dos
    droite du déjà été étant étions été étée étées étés étiez étaient étais
    était êtes elle elles en encore es est et etaient etais etait etions etiez
    etre eu eue eues eurent eus eut eux fait faire fais faisaient faisais faisait
    font fussent ha hein his hui il ils je juste la le leur leurs les leur loin
    lui ma maint maintenant mais mes me mine moins moi mon même ne nos notre nous
    on ont or ou où par pas peut peu peux pour pourquoi pres qu quand que qui
    quoi sans sa se sera serai seraient serais serait sera seras seront ses soi
    soit son sont sous sur ta te tes tienne tiennes tiens toi ton toujours tous
    tout toute toutes trop trés tu un une uns us va vais vait vers via voici
    voila vos votre vous vu y à étais étions été étiez être avais avait avions
    aviez avons aurez auront aurait aurions avaient ayant été eue eues eus eut
    furent fussent ont sera seront serait seraient sont sommes suis es est et
    ni ou si très oui non chez donc afee deja
    monsieur madame mme mlle m me
    """.split()
)