document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    socket.on('connect', () => {
        console.log('Connected to server');
    });

    socket.on('alert', (data) => {
        alert(`New Alert: ${data.alert_type} in ${data.zone_name}`);
    });
});
