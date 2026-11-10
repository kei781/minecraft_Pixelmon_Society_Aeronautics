// QA only. Install after an authenticated player has joined, then kubejs reload server_scripts.
// Observe public static accessor IDs/types without reading player values or changing data.
var psaSchemaReported = false;
ServerEvents.tick(event => {
    if (psaSchemaReported) return;
    psaSchemaReported = true;
    try {
        var psaPixelmonClass = Java.loadClass('com.pixelmonmod.pixelmon.listener.EntityPlayerExtension');
        var psaCarryClass = Java.loadClass('tschipp.carryon.common.carry.CarryOnDataManager');
        var psaSerializersClass = Java.loadClass('net.minecraft.network.syncher.EntityDataSerializers');
        var psaConstant = function(mapped, srg) {
            try {
                var value = psaSerializersClass[mapped];
                if (value != null) return value;
            } catch (error) { /* Try the pinned runtime name below. */ }
            return psaSerializersClass[srg];
        };
        var psaId = function(key) {
            try { return key.getId(); } catch (error) { return key.m_135015_(); }
        };
        var psaSerializer = function(key) {
            try { return key.getSerializer(); } catch (error) { return key.m_135016_(); }
        };
        var psaKinds = [[psaConstant('STRING', 'f_135030_'), 'string'],
                       [psaConstant('BYTE', 'f_135027_'), 'byte'],
                       [psaConstant('COMPOUND_TAG', 'f_135042_'), 'compound']];
        var psaNames = ['dwPokeballs', 'dwMegaItem', 'dwMegaItemsUnlocked', 'dwShinyCharm', 'dwOvalCharm',
                       'dwExpCharm', 'dwCatchingCharm', 'dwMarkCharm', 'dwHween'];
        var psaKeys = [['CARRY_DATA_KEY', psaCarryClass.CARRY_DATA_KEY]];
        psaNames.forEach(name => psaKeys.push([name, psaPixelmonClass[name]]));
        var psaFields = psaKeys.map(entry => {
            var wire = psaSerializer(entry[1]);
            var kind = 'other';
            psaKinds.forEach(pair => { if (wire.equals(pair[0])) kind = pair[1]; });
            return {field: entry[0], id: psaId(entry[1]), serializer: kind};
        });
        console.info('PSA_NATURAL_SERVER_PLAYER_SCHEMA ' + JSON.stringify(psaFields));
    } catch (error) {
        console.error('PSA_NATURAL_SERVER_PLAYER_SCHEMA_FAILED ' + error);
    }
});
