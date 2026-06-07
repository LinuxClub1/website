//same config as my site im lazy
particlesJS('particles-js', {
  "particles": {
    "number": {
      "value": 80,
      "density": {
        "enable": true,
        "value_area": 800
      }
    },
    "color": {
      "value": "#ffffff"
    },
    "shape": {
      "type": "circle"
    },
    "opacity": {
      "value": 0.5,
      "random": false
    },
    "size": {
      "value": 3,
      "random": true
    },
    "line_linked": {
      "enable": true,
      "distance": 150,
      "color": "#ffffff",
      "opacity": 0.4,
      "width": 1
    },
    "move": {
      "enable": true,
      "speed": 6,
      "direction": "none",
      "random": false,
      "straight": false,
      "out_mode": "out",
      "bounce": false
    }
  },
  "interactivity": {
    "detect_on": "canvas",
    "events": {
      "onhover": {
        "enable": true,
        "mode": "repulse"
      },
      "onclick": {
        "enable": true,
        "mode": "push"
      },
      "resize": true
    },
    "modes": {
      "repulse": {
        "distance": 200,
        "duration": 0.4
      },
      "push": {
        "particles_nb": 4
      }
    }
  },
  "retina_detect": true
});


document.addEventListener('DOMContentLoaded', () => {
    //dropdown stuff
    const dropdowns = document.querySelectorAll('.custom-select');

    dropdowns.forEach(dropdown => {
        const trigger = dropdown.querySelector('.select-trigger');
        const triggerText = trigger.querySelector('span');
        const options = dropdown.querySelectorAll('.option');
        const hiddenInput = dropdown.querySelector('input[type="hidden"]');

        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdowns.forEach(other => {
                if (other !== dropdown) other.classList.remove('open');
            });
            dropdown.classList.toggle('open');
        });

        options.forEach(option => {
            option.addEventListener('click', (e) => {
                e.stopPropagation();
                const selectedValue = option.getAttribute('data-value');
                const selectedText = option.textContent;

                triggerText.textContent = selectedText;
                hiddenInput.value = selectedValue;
                triggerText.classList.remove('placeholder');
                
                trigger.classList.remove('error-uhoh');
                
                dropdown.classList.remove('open');
            });
        });
    });

    window.addEventListener('click', () => {
        dropdowns.forEach(dropdown => dropdown.classList.remove('open'));
    });


    const form = document.querySelector('.form-container');
    const emailField = document.getElementById('email-field');
    const emailError = document.getElementById('email-error');
    const formMessage = document.getElementById('form-message');

    form.addEventListener('submit', async (e) => {
        e.preventDefault(); 
        
        let isFormValid = true;

        formMessage.style.display = 'none';
        formMessage.textContent = '';

        const requiredInputs = form.querySelectorAll('input[required]:not([type="hidden"]), textarea[required]');
        requiredInputs.forEach(input => {
            if (!input.value.trim()) {
                input.classList.add('error-uhoh');
                isFormValid = false;
            } else {
                input.classList.remove('error-uhoh');
            }
            
            input.addEventListener('input', () => input.classList.remove('error-uhoh'));
        });

        dropdowns.forEach(dropdown => {
            const hiddenInput = dropdown.querySelector('input[type="hidden"]');
            const trigger = dropdown.querySelector('.select-trigger');
            
            if (hiddenInput.hasAttribute('required') && !hiddenInput.value) {
                trigger.classList.add('error-uhoh');
                isFormValid = false;
            } else {
                trigger.classList.remove('error-uhoh');
            }
        });

        if (emailField.value.trim()) {
            const emailValue = emailField.value.trim().toLowerCase();
            if (!emailValue.endsWith('@bvsd.org')) {
                emailField.classList.add('error-uhoh');
                emailError.style.display = 'block';
                isFormValid = false;
            } else {
                emailError.style.display = 'none';
            }
        }

        emailField.addEventListener('input', () => {
            emailField.classList.remove('error-uhoh');
            emailError.style.display = 'none';
        });

        if (!isFormValid) return;

        //send to server stuff

        const firstName = form.querySelectorAll('input[type="text"]')[0].value.trim();
        const lastName = form.querySelectorAll('input[type="text"]')[1].value.trim();
        const referralSource = form.querySelectorAll('input[type="text"]')[2].value.trim();

        const formData = {
            name: `${firstName} ${lastName}`,
            email: emailField.value.trim(),
            grade: document.getElementById('grade').value,
            availability: document.getElementById('availability').value,
            found: referralSource,
            reason: document.getElementById('whyjoin').value.trim(),
            else: document.getElementById('notes').value.trim()
        };

        try {
            const response = await fetch('http://fhselectronics.dev:3000/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            if (response.ok) {
                formMessage.style.color = 'var(--accent)';
                formMessage.textContent = 'Submitted successfully';
                formMessage.style.display = 'block';
                
                form.reset();
                
                document.querySelectorAll('.select-trigger span').forEach(span => {
                    if(span.textContent.includes('grade')) span.textContent = 'Select grade';
                    if(span.textContent.includes('availability')) span.textContent = 'Select availability';
                    span.classList.add('placeholder');
                });
            } else {
                formMessage.style.color = '#ef4444';
                formMessage.textContent = 'Server error';
                formMessage.style.display = 'block';
            }
        } catch (error) {
            console.error('Submission Error:', error);
            formMessage.style.color = '#ef4444';
            formMessage.textContent = 'Could not connect to server (i blame peap)';
            formMessage.style.display = 'block';
        }
    });
});