import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { modelService } from '../../services/models.service';
import Navbar from '../navbar/navbar';
import Sidebar from '../Sidebar/Sidebar';
import SimpleLoader from '../common/SimpleLoader';
import './ConfigureModels.css';

const ConfigureModels = () => {
    const navigate = useNavigate();
    const [models, setModels] = useState([]);
    const [providers, setProviders] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [user, setUser] = useState(null);
    const [showForm, setShowForm] = useState(false);
    const [editingModel, setEditingModel] = useState(null);
    const [formData, setFormData] = useState({
        provider: '',
        model_name: '',
        display_name: '',
        api_key: '',
        base_url: ''
    });

    useEffect(() => {
        const userData = localStorage.getItem('userData');
        if (userData) {
            const parsedUser = JSON.parse(userData);
            setUser(parsedUser);
            if (parsedUser.role !== 'super_admin') {
                navigate('/overview');
                return;
            }
        } else {
            navigate('/login');
            return;
        }
        loadData();
    }, [navigate]);

    const loadData = async () => {
        try {
            setLoading(true);
            const [modelsRes, providersRes] = await Promise.all([
                modelService.getAllModels(),
                modelService.getProviders()
            ]);
            setModels(modelsRes.models || []);
            setProviders(providersRes.providers || []);
        } catch (err) {
            setError('Failed to load data');
        } finally {
            setLoading(false);
        }
    };

    const resetForm = () => {
        setFormData({
            provider: '',
            model_name: '',
            display_name: '',
            api_key: '',
            base_url: ''
        });
        setEditingModel(null);
        setShowForm(false);
    };

    const handleEdit = (model) => {
        setFormData({
            provider: model.provider,
            model_name: model.model_name,
            display_name: model.display_name || '',
            api_key: '',
            base_url: model.base_url || ''
        });
        setEditingModel(model);
        setShowForm(true);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            setSaving(true);
            const payload = { ...formData };
            if (!payload.api_key && editingModel) {
                delete payload.api_key;
            }
            if (editingModel) {
                await modelService.updateModel(editingModel.id, payload);
            } else {
                await modelService.createModel(payload);
            }
            resetForm();
            await loadData();
        } catch (err) {
            alert(`Error saving model: ${err.response?.data?.error || err.message}`);
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (model) => {
        if (!window.confirm(`Delete model "${model.display_name || model.model_name}"?`)) return;
        try {
            await modelService.deleteModel(model.id);
            await loadData();
        } catch (err) {
            alert(`Error deleting model: ${err.response?.data?.error || err.message}`);
        }
    };

    const formatDate = (dateString) => {
        if (!dateString) return 'N/A';
        return new Date(dateString).toLocaleDateString('en-US', {
            year: 'numeric', month: 'short', day: 'numeric'
        });
    };

    if (loading) {
        return (
            <div className="configure-models-page">
                <Navbar />
                <div className="configure-models-container">
                    <Sidebar />
                    <div className="configure-models-content">
                        <SimpleLoader message="Loading models..." />
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="configure-models-page">
            <Navbar />
            <div className="configure-models-container">
                <Sidebar />
                <div className="configure-models-content">
                    <div className="configure-models-header">
                        <h1>Configure AI Models</h1>
                        <p className="header-subtitle">Add, edit, and manage AI models across all providers</p>
                        {error && <div className="error-message">{error}</div>}
                        <button className="add-model-btn" onClick={() => { resetForm(); setShowForm(!showForm); }}>
                            {showForm ? 'Cancel' : '+ Add Model'}
                        </button>
                    </div>

                    {showForm && (
                        <div className="model-form-overlay">
                            <div className="model-form-card">
                                <h2>{editingModel ? 'Edit Model' : 'Add New Model'}</h2>
                                <form onSubmit={handleSubmit}>
                                    <div className="form-row">
                                        <div className="form-group">
                                            <label>Provider *</label>
                                            <select
                                                value={formData.provider}
                                                onChange={(e) => setFormData({...formData, provider: e.target.value})}
                                                required
                                            >
                                                <option value="">Select provider</option>
                                                    {providers.map((p) => (
                                                    <option key={p.id} value={p.id}>{p.name}</option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>
                                    <div className="form-row">
                                        <div className="form-group">
                                            <label>Model Name *</label>
                                            <input
                                                type="text"
                                                value={formData.model_name}
                                                onChange={(e) => setFormData({...formData, model_name: e.target.value})}
                                                placeholder="e.g. gpt-4o"
                                                required
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>Display Name</label>
                                            <input
                                                type="text"
                                                value={formData.display_name}
                                                onChange={(e) => setFormData({...formData, display_name: e.target.value})}
                                                placeholder="e.g. GPT-4o"
                                            />
                                        </div>
                                    </div>
                                    <div className="form-row">
                                        <div className="form-group">
                                            <label>API Key {editingModel && '(leave blank to keep existing)'}</label>
                                            <input
                                                type="password"
                                                value={formData.api_key}
                                                onChange={(e) => setFormData({...formData, api_key: e.target.value})}
                                                placeholder={editingModel ? 'Enter new API key or leave blank' : 'Enter API key'}
                                                required={!editingModel}
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>Base URL (optional)</label>
                                            <input
                                                type="text"
                                                value={formData.base_url}
                                                onChange={(e) => setFormData({...formData, base_url: e.target.value})}
                                                placeholder="e.g. https://api.openai.com/v1"
                                            />
                                        </div>
                                    </div>
                                    <div className="form-actions">
                                        <button type="submit" className="btn-save" disabled={saving}>
                                            {saving ? 'Saving...' : (editingModel ? 'Update Model' : 'Add Model')}
                                        </button>
                                        <button type="button" className="btn-cancel" onClick={resetForm}>Cancel</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    )}

                    <div className="models-table-wrapper">
                        <table className="models-table">
                            <thead>
                                <tr>
                                    <th>Provider</th>
                                    <th>Model Name</th>
                                    <th>Display Name</th>
                                    <th>Created</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {models.length === 0 ? (
                                    <tr>
                                        <td colSpan="5" className="no-models">No models configured yet. Click "Add Model" to get started.</td>
                                    </tr>
                                ) : (
                                    models.map((model) => (
                                        <tr key={model.id}>
                                            <td>{model.provider}</td>
                                            <td><code>{model.model_name}</code></td>
                                            <td>{model.display_name || '-'}</td>
                                            <td>{formatDate(model.created_at)}</td>
                                            <td className="actions-cell">
                                                <button className="btn-edit" onClick={() => handleEdit(model)}>Edit</button>
                                                <button className="btn-delete" onClick={() => handleDelete(model)}>Delete</button>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ConfigureModels;