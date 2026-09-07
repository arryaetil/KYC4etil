export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Ubuntu", "Arial", "sans-serif"],
      },
      colors: {
        // Basispalet uit de ibc-brandgids (p32). Etil is het Data-onderdeel,
        // dus de warme kleurwereld rood-geel is de onze.
        night: "#121212",
        seasalt: "#F8F9FA",

        // De bestaande tokennamen blijven staan zodat de ruim 240
        // verwijzingen in de views niet allemaal hoeven te wijzigen.
        ink: "#121212",
        line: "#E3E5E7",
        panel: "#F8F9FA",
        etil: "#121212", // primaire actie is Night, niet een spectrumkleur

        // Night op 85/65/50/25% over Seasalt (p32), uitgerekend naar vaste
        // hex. Vervangt slate-*; twee grijzen door elkaar leest onrustig.
        mist: {
          85: "#353535",
          65: "#636364",
          50: "#858586",
          25: "#BEBFBF",
        },

        // Het ibc-spectrum (p33). Spaarzaam en met hoog contrast: in het
        // werkscherm alleen als statuskleur en als hairline onder de header.
        spectrum: {
          violet: "#330099",
          deepblue: "#000099",
          trueblue: "#0066cc",
          green: "#009966",
          red: "#ff3333",
          orange: "#ff6600",
          yellow: "#ffff33",
        },

        // Leesbare tekstvarianten van de drie statuskleuren. De spectrum-
        // waarden zelf halen op wit geen AA voor kleine tekst (#009966 komt
        // niet verder dan 3,1:1), dus voor tekst een donkerder variant van
        // dezelfde kleur. Vlakken en randen gebruiken het spectrum wel, met
        // een dekkingswaarde.
        gekozen: "#045F45",
        aandacht: "#8A3800",
        fout: "#A31414",
        // Op Night moet het juist de andere kant op: daar is een donkerrood
        // onleesbaar en werkt een lichte variant.
        foutlicht: "#FFBCBC",
      },
    },
  },
  plugins: [],
};
