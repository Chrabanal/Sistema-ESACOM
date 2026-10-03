import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'cl.esacom.crm',
  appName: 'ESACOM',
  webDir: 'dist',
  android: {
    // Se instala como APK directo en el teléfono del vendedor (sideload),
    // sin pasar por Google Play -- ver plan de sprint, Día 12.
    allowMixedContent: false,
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 1200,
      backgroundColor: '#DA291C', // rojo de marca ESACOM, no los colores del logo
      androidSplashResourceName: 'splash',
      showSpinner: false,
    },
  },
};

export default config;
