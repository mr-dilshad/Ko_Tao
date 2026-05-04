document.addEventListener('DOMContentLoaded', () => {
    // Navbar Scroll Effect
    const navbar = document.querySelector('.navbar');
    
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.style.background = 'rgba(2, 48, 71, 0.98)';
            navbar.style.boxShadow = '0 4px 20px rgba(0,0,0,0.1)';
            navbar.style.padding = '10px 0';
        } else {
            navbar.style.background = 'rgba(2, 48, 71, 0.95)';
            navbar.style.boxShadow = 'none';
            navbar.style.padding = '15px 0';
        }
    });

    // Mobile Menu Toggle
    const hamburger = document.querySelector('.hamburger');
    const navLinks = document.querySelector('.nav-links');

    if (hamburger) {
        hamburger.addEventListener('click', () => {
            navLinks.classList.toggle('active');
            const icon = hamburger.querySelector('i');
            if (navLinks.classList.contains('active')) {
                icon.classList.remove('fa-bars');
                icon.classList.add('fa-xmark');
            } else {
                icon.classList.remove('fa-xmark');
                icon.classList.add('fa-bars');
            }
        });
    }

    // Close mobile menu when clicking a link
    document.querySelectorAll('.nav-links a').forEach(link => {
        link.addEventListener('click', () => {
            navLinks.classList.remove('active');
            const icon = hamburger.querySelector('i');
            if (icon) {
                icon.classList.remove('fa-xmark');
                icon.classList.add('fa-bars');
            }
        });
    });

    // Form Submission
    const inquiryForm = document.getElementById('inquiryForm');
    const paymentModal = document.getElementById('payment-modal');
    const paymentForm = document.getElementById('payment-form');
    
    if (inquiryForm) {
        inquiryForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = inquiryForm.querySelector('button[type="submit"]');
            const originalText = btn.innerHTML;
            
            // Loading state
            btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Initializing Booking...';
            btn.disabled = true;

            const formData = {
                name: document.getElementById('name').value,
                email: document.getElementById('email').value,
                course_id: document.getElementById('course_id').value,
                dorm_id: document.getElementById('dorm_id').value,
                check_in_date: document.getElementById('check_in_date').value,
                coupon_code: document.getElementById('coupon_code').value
            };
            
            try {
                const response = await fetch('/api/book', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });
                const result = await response.json();
                
                if (result.success) {
                    // Open Payment Modal
                    document.getElementById('payment-booking-id').value = result.booking_id;
                    document.getElementById('payment-booking-ref').innerText = result.booking_ref;
                    document.getElementById('payment-total-price').innerText = '$' + result.total_price.toFixed(2);
                    
                    paymentModal.style.display = 'flex';
                    
                    // Reset button
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                } else {
                    handleBookingError(result, btn, originalText);
                }
            } catch (err) {
                console.error(err);
                btn.innerHTML = '<i class="fa-solid fa-xmark"></i> Error processing';
                btn.disabled = false;
            }
        });
    }

    // Payment Logic
    if (paymentForm) {
        paymentForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('pay-button');
            const originalText = btn.innerHTML;
            
            btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Processing Secure Payment...';
            btn.disabled = true;

            const bookingId = document.getElementById('payment-booking-id').value;
            
            try {
                const response = await fetch('/api/pay', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ booking_id: bookingId })
                });
                const result = await response.json();
                
                if (result.success) {
                    paymentForm.style.display = 'none';
                    document.getElementById('payment-success-msg').style.display = 'block';
                    inquiryForm.reset();
                } else {
                    alert(result.error || 'Payment failed');
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }
            } catch (err) {
                console.error(err);
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        });

        document.getElementById('cancel-payment').addEventListener('click', () => {
            paymentModal.style.display = 'none';
        });
    }

    function handleBookingError(result, btn, originalText) {
        if (result.error && result.error.toLowerCase().includes('coupon')) {
            const errorBox = document.getElementById('coupon-error');
            const couponInput = document.getElementById('coupon_code');
            if (errorBox && couponInput) {
                errorBox.querySelector('span').innerText = result.error;
                errorBox.style.display = 'block';
                couponInput.style.borderColor = '#d32f2f';
                couponInput.style.backgroundColor = '#ffebee';
                couponInput.animate([
                    { transform: 'translateX(0)' },
                    { transform: 'translateX(-6px)' },
                    { transform: 'translateX(6px)' },
                    { transform: 'translateX(0)' }
                ], { duration: 300 });
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        } else {
            btn.innerHTML = '<i class="fa-solid fa-xmark"></i> ' + (result.error || 'Error');
            setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 3000);
        }
    }

    // Real-time coupon validation on blur
    const couponCodeInput = document.getElementById('coupon_code');
    const couponErrorBox = document.getElementById('coupon-error');
    
    if (couponCodeInput) {
        couponCodeInput.addEventListener('blur', async function() {
            const code = this.value.trim();
            if (!code) return;

            const checkIn = document.getElementById('check_in_date')?.value || '';
            try {
                const res = await fetch('/api/validate-coupon?code=' + encodeURIComponent(code) + '&check_in=' + encodeURIComponent(checkIn));
                const data = await res.json();
                if (data.valid) {
                    couponErrorBox.style.display = 'none';
                    couponCodeInput.style.borderColor = '#2e7d32';
                    couponCodeInput.style.backgroundColor = '#f1f8e9';
                    couponErrorBox.querySelector('span').innerText = '';
                } else {
                    couponErrorBox.querySelector('span').innerText = data.error;
                    couponErrorBox.style.display = 'block';
                    couponCodeInput.style.borderColor = '#d32f2f';
                    couponCodeInput.style.backgroundColor = '#ffebee';
                }
            } catch(e) {}
        });

        couponCodeInput.addEventListener('input', function() {
            couponErrorBox.style.display = 'none';
            couponCodeInput.style.borderColor = '';
            couponCodeInput.style.backgroundColor = '';
        });
    }
    const couponsModal = document.getElementById('coupons-modal');
    const viewCouponsLink = document.getElementById('view-coupons-link');
    const closeCouponsModal = document.getElementById('close-coupons-modal');
    
    if (viewCouponsLink && couponsModal) {
        viewCouponsLink.addEventListener('click', function(e) {
            e.preventDefault();
            couponsModal.style.display = 'flex';
        });
    }
    
    if (closeCouponsModal && couponsModal) {
        closeCouponsModal.addEventListener('click', function() {
            couponsModal.style.display = 'none';
        });
    }
    
    // Course Slider Logic
    const slider = document.getElementById('course-slider');
    const prevBtn = document.getElementById('course-prev');
    const nextBtn = document.getElementById('course-next');

    if (slider && prevBtn && nextBtn) {
        nextBtn.addEventListener('click', () => {
            slider.scrollBy({ left: 350, behavior: 'smooth' });
        });

        prevBtn.addEventListener('click', () => {
            slider.scrollBy({ left: -350, behavior: 'smooth' });
        });

        // Hide/Show arrows based on scroll position
        const toggleArrows = () => {
            prevBtn.style.opacity = slider.scrollLeft <= 0 ? '0' : '1';
            prevBtn.style.pointerEvents = slider.scrollLeft <= 0 ? 'none' : 'auto';
            
            const isAtEnd = slider.scrollLeft + slider.clientWidth >= slider.scrollWidth - 10;
            nextBtn.style.opacity = isAtEnd ? '0' : '1';
            nextBtn.style.pointerEvents = isAtEnd ? 'none' : 'auto';
        };

        slider.addEventListener('scroll', toggleArrows);
        window.addEventListener('resize', toggleArrows);
        setTimeout(toggleArrows, 500); // Initial check
    }
});

// Global function to apply coupon from modal
function applyCoupon(code) {
    const couponInput = document.getElementById('coupon_code');
    if (couponInput) {
        couponInput.value = code;
    }
    const modal = document.getElementById('coupons-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}
