const { Gpio } = require('onoff');

async function getGpioOffset() {
    try {
        // Read the base value from gpiochip512
        const fs = require('fs');
        const base = parseInt(fs.readFileSync('/sys/class/gpio/gpiochip512/base').toString());
        console.log(`GPIO chip base offset: ${base}`);
        return base;
    } catch (err) {
        console.error('Error reading GPIO chip base:', err);
        return 512; // Default fallback for RPi 5
    }
}

async function setupGpio() {
    try {
        const baseOffset = await getGpioOffset();
        const PIN = 20;
        const adjustedPin = baseOffset + PIN;
        
        console.log(`Attempting to initialize GPIO ${PIN} (adjusted to ${adjustedPin})`);
        
        // Initialize GPIO with adjusted pin number
        const pin = new Gpio(adjustedPin, 'in', 'both');
        
        console.log('Successfully initialized GPIO');
        console.log('Monitoring for changes...');
        
        pin.watch((err, value) => {
            if (err) {
                console.error('Error watching GPIO:', err);
                return;
            }
            console.log(`GPIO ${PIN} value: ${value}`);
        });
        
        process.on('SIGINT', () => {
            pin.unexport();
            console.log('\nCleaning up...');
            process.exit(0);
        });
        
    } catch (err) {
        console.error('Error:', err);
        console.log('\nDiagnostic information:');
        try {
            const fs = require('fs');
            const gpioContents = fs.readdirSync('/sys/class/gpio');
            console.log('Available GPIO chips:', gpioContents);
            
            // Try to read more information about the GPIO chips
            if (fs.existsSync('/sys/class/gpio/gpiochip512/label')) {
                const chip512Label = fs.readFileSync('/sys/class/gpio/gpiochip512/label', 'utf8');
                const chip512Ngpio = fs.readFileSync('/sys/class/gpio/gpiochip512/ngpio', 'utf8');
                console.log('gpiochip512 label:', chip512Label.trim());
                console.log('gpiochip512 number of GPIOs:', chip512Ngpio.trim());
            }
            
            if (fs.existsSync('/sys/class/gpio/gpiochip570/label')) {
                const chip570Label = fs.readFileSync('/sys/class/gpio/gpiochip570/label', 'utf8');
                const chip570Ngpio = fs.readFileSync('/sys/class/gpio/gpiochip570/ngpio', 'utf8');
                console.log('gpiochip570 label:', chip570Label.trim());
                console.log('gpiochip570 number of GPIOs:', chip570Ngpio.trim());
            }
        } catch (diagErr) {
            console.error('Could not get diagnostic information:', diagErr);
        }
    }
}

setupGpio();
