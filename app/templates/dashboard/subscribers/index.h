h{% extends "base.html" %}
{% block content %}
<div class="p-4 md:p-8">
    <div class="flex justify-between items-center mb-8">
        <div>
            <h1 class="text-3xl font-bold">Subscribers</h1>
            <p class="text-gray-500">Email subscribers management</p>
        </div>
        <a href="/dashboard" class="bg-black text-white px-5 py-3 rounded-xl">Dashboard</a>
    </div>

    <!-- SUBSCRIBERS TABLE -->
    <div class="overflow-x-auto bg-white rounded-2xl shadow">
        <table class="w-full">
            <thead class="bg-gray-100">
                <tr>
                    <th class="p-4 text-left">ID</th>
                    <th class="p-4 text-left">Email</th>
                    <th class="p-4 text-left">Subscribed At</th>
                    <th class="p-4 text-left">Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for subscriber in subscribers %}
                <tr class="border-t">
                    <td class="p-4">{{ subscriber.id }}</td>
                    <td class="p-4">{{ subscriber.email|e }}</td>
                    <td class="p-4">
                        {{ subscriber.subscribed_at.strftime('%d %b %Y %H:%M') if subscriber.subscribed_at }}
                    </td>
                    <td class="p-4">
                        <!-- Delete as POST form -->
                        <form method="post" action="/subscribers/delete/{{ subscriber.id }}" 
                              class="inline" onsubmit="return confirm('Delete this subscriber?')">
                            <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                            <button type="submit" class="bg-red-500 hover:bg-red-600 text-white px-3 py-2 rounded-lg">
                                Delete
                            </button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endblock %}
